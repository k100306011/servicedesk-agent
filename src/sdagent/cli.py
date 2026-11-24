"""Command line: python -m sdagent <command>.
assess-data, run, batch, eval, summarize and reset. Every command takes --profile offline|local|azure.
offline needs no model and runs B0, so anyone can try the prototype without keys.
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from . import ROOT


def common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--profile", choices=["offline", "local", "azure"], default=None)
    p.add_argument("--config", choices=["B0", "B1", "B2", "B3"], default=None,
                   help="default: B3 with a model, B0 when offline")


def resolve(args) -> tuple[str, str]:
    profile = args.profile or os.getenv("LLM_PROFILE", "offline").split("#")[0].strip()
    config = args.config or ("B0" if profile == "offline" else "B3")
    if profile == "offline" and config != "B0":
        sys.exit("B1-B3 need a model: use --profile local or --profile azure")
    return profile, config


def main(argv: list[str] | None = None) -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(prog="sdagent", description="IT service desk triage agent prototype")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("assess-data", help="data assessment -> docs/data_assessment.md")
    p = sub.add_parser("run", help="process one request")
    p.add_argument("--id", help="request ID, e.g. NEW-005, INC-1013, NEW-002-C, RT-03")
    p.add_argument("--text", help="free text instead of an ID")
    p.add_argument("--channel", default="chat")
    p.add_argument("--explain", action="store_true", help="print the trace step by step")
    common(p)
    p = sub.add_parser("batch", help="process a set and write to SQLite (review console)")
    p.add_argument("--set", default="incoming")
    common(p)
    p = sub.add_parser("eval", help="run a configuration over a set and score it")
    p.add_argument("--set", default="dev", help="incoming | historical | dev | holdout | redteam | final")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--tag", default="dev", help="label for this round, e.g. dev, tune1, final, latency")
    p.add_argument("--concurrency", type=int, default=4)
    common(p)
    sub.add_parser("summarize", help="recompute every number from results/")
    sub.add_parser("reset", help="rebuild the SQLite database")
    args = ap.parse_args(argv)

    if args.cmd == "assess-data":
        from .assess import run as assess_run
        facts = assess_run()
        print(f"wrote docs/data_assessment.md and results/data_facts.json "
              f"({facts['historical']['rows']} tickets, {facts['incoming']['rows']} requests, {facts['kb']['articles']} KB)")
    elif args.cmd == "run":
        from .pipeline import find_request, free_text_request, run_request
        from .explain import explain, short
        profile, config = resolve(args)
        req = find_request(args.id) if args.id else free_text_request(args.text, args.channel)
        trace = run_request(req, config=config, profile=profile)
        print(explain(trace) if args.explain else short(trace))
    elif args.cmd == "batch":
        from .pipeline import load_set, run_request
        from .explain import batch_table
        from . import actions
        profile, config = resolve(args)
        db = actions.connect()
        traces = [run_request(r, config=config, profile=profile, db=db) for r in load_set(args.set)]
        print(batch_table(traces))
    elif args.cmd == "eval":
        sys.path.insert(0, str(ROOT))
        from eval.run_eval import run_eval
        profile, config = resolve(args)
        run_eval(config, profile, args.set, args.runs, args.tag, args.concurrency)
    elif args.cmd == "summarize":
        sys.path.insert(0, str(ROOT))
        from eval.report import summarize
        summarize()
    elif args.cmd == "reset":
        from . import actions
        actions.reset()
        print("SQLite database rebuilt:", actions.DB_PATH.relative_to(ROOT))
