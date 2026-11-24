"""Run one configuration over a set N times and write raw results to results/runs/*.jsonl.
Each run gets its own SQLite file, so runs never see each other's tickets.
Checks read what was really stored (tickets, messages, audit log, traces), not only the decision.
Fake secrets from the rubric are masked in the results file after the checks ran.
"""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml

from sdagent import ROOT, actions, pipeline
from sdagent.data import historical_tickets, read_csv
from sdagent.models import ACTIONS

from eval.checks import bucket, check_item

EVAL, RUNS = ROOT / "eval", ROOT / "results" / "runs"
SETS = {"dev": ["incoming", "historical"], "final": ["holdout", "redteam"]}


def load_gold() -> dict[str, dict]:
    inc = yaml.safe_load((EVAL / "gold_incoming.yaml").read_text(encoding="utf-8"))
    ho = yaml.safe_load((EVAL / "gold_holdout.yaml").read_text(encoding="utf-8"))
    gold = dict(inc)
    for k, v in ho["holdout"].items():
        gold[k] = {**inc[v["parent"]], **{kk: vv for kk, vv in v.items() if kk != "parent"}, "parent": v["parent"]}
    gold.update(ho["redteam"])
    return gold


def historical_labels() -> dict[str, dict]:
    audit = {a["ticket_id"]: a for a in read_csv(EVAL / "label_audit.csv")}
    out = {}
    for t in historical_tickets():
        a = audit.get(t["ticket_id"])
        fixed = {k: (a[f"suggested_{k}"] if a else t[k if k != "team" else "assigned_team"]).split("|")
                 for k in ("category", "team", "priority")}
        out[t["ticket_id"]] = {"original": {"category": [t["category"]], "team": [t["assigned_team"]], "priority": [t["priority"]]},
                               "corrected": fixed}
    return out


def label_scores(d: dict, labels: dict) -> dict:
    return {f"{which}_{k}_ok": (d[k] in lab[k] if k != "priority" else bucket(d[k]) in {bucket(p) for p in lab[k]})
            for which, lab in labels.items() for k in ("category", "team", "priority")}


def stored_rows(db, item: str) -> list[dict]:
    tids = [r["id"] for r in db.execute("SELECT id FROM tickets WHERE request_id=?", (item,))]
    rows = []
    for table, col in (("tickets", "request_id"), ("messages", "request_id"), ("links", "request_id"),
                       ("security_notices", "request_id"), ("traces", "request_id"), ("audit_log", "request_id")):
        rows += [{"table": table, **dict(r)} for r in db.execute(f"SELECT * FROM {table} WHERE {col}=?", (item,))]
    rows += [{"table": "audit_log", **dict(r)} for t in tids for r in db.execute("SELECT * FROM audit_log WHERE request_id=?", (t,))]
    return rows


def process(req, config, profile, db, gold, labels) -> dict:
    t = pipeline.run_request(req, config=config, profile=profile, db=db)
    with actions.LOCK:  # one SQLite connection is shared by the worker threads
        rows = stored_rows(db, req.request_id)
    tickets = [{k: r[k] for k in ("id", "kind", "status", "category", "priority", "team", "incident_id")}
               for r in rows if r["table"] == "tickets"]
    r = {"item": req.request_id, "set": req.source, "channel": req.channel, "message": req.message,
         "decision": t.decision.model_dump(), "pre_guard": t.pre_guard.model_dump() if t.pre_guard else None,
         "guard_fixes": t.guard_fixes, "actions": t.actions, "tickets": tickets, "canary": t.canary,
         "injection": (t.step("1 sanitize").output or {}).get("injection", []),
         "security_notified_injection": any(r["table"] == "security_notices" and "injection" in r["reason"] for r in rows),
         "correlation": (t.step("3 correlate").output if t.step("3 correlate") else None),
         "latency_ms": t.total_ms, "tokens": t.tokens, "steps_ms": {s.name: s.ms for s in t.steps},
         "stored_text": json.dumps(rows, ensure_ascii=False)}
    g = gold.get(req.request_id) or {"action": ACTIONS}
    r["checks"] = check_item(r, g)
    if req.request_id in labels:
        r["labels"] = label_scores(r["decision"], labels[req.request_id])
    for secret in g.get("secrets", []):  # keep fake secrets out of the committed results
        r = json.loads(json.dumps(r, ensure_ascii=False).replace(secret, "[FAKE-SECRET]"))
    del r["stored_text"]
    return r


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def run_eval(config: str, profile: str, set_name: str, runs: int, tag: str, concurrency: int) -> list[Path]:
    gold, labels, written = load_gold(), historical_labels(), []
    reqs = [r for s in SETS.get(set_name, [set_name]) for r in pipeline.load_set(s)]
    RUNS.mkdir(parents=True, exist_ok=True)
    for k in range(1, runs + 1):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        db_path = ROOT / "runtime" / "eval" / f"{tag}_{config}_{set_name}_{profile}_r{k}_{stamp}.db"
        db = actions.connect(db_path)
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
            results = list(pool.map(lambda r: process(r, config, profile, db, gold, labels), reqs))
        meta = {"tag": tag, "config": config, "profile": profile, "set": set_name, "run": k, "items": len(results),
                "concurrency": concurrency, "seconds": round(time.time() - t0, 1), "commit": git_commit(),
                "model": getattr(pipeline._LLM.get(profile), "model", "rules"), "started": stamp}
        out = RUNS / f"{tag}__{config}__{set_name}__{profile}__r{k}__{stamp}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            f.write(json.dumps({"meta": meta}, ensure_ascii=False) + "\n")
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        crit = sum(sum(r["checks"]["critical"].values()) for r in results)
        print(f"{out.name}: {len(results)} items, {meta['seconds']} s, critical violations {crit}")
        written.append(out)
    return written
