"""Cost model from real B3 calls: python -m eval.cost
The local model counts tokens with the Qwen tokenizer, which is not what Azure bills. This script recounts the
prompts and replies that B3 really sent and received (results/llm_calls/*.jsonl[.gz], written with SDAGENT_LLM_LOG)
with the GPT tokenizer o200k_base, shows both counts, and prices them. Writes results/cost_tokens.csv,
results/cost_summary.json and docs/cost_model.md.
"""
from __future__ import annotations

import csv
import gzip
import json

import tiktoken

from sdagent import ROOT
from sdagent.llm import strict_schema
from sdagent.models import Decision, Understanding

CALLS = ROOT / "results" / "llm_calls"
CHECKED = "2026-11-24"
SOURCE = "https://azure.microsoft.com/en-us/pricing/details/azure-openai/"
# USD per 1M tokens (input, cached input, output), short context, Standard. Copied from the official pricing page above.
PRICES = {"gpt-6-luna, Global": (0.10, 0.01, 0.50), "gpt-6-luna, Data Zone": (0.11, 0.011, 0.55),
          "gpt-6.2-sol, Global": (2.00, 0.10, 10.00), "gpt-6.2-sol, Data Zone": (2.20, 0.11, 11.00)}
VOLUMES = [10_000, 50_000]
MINUTES_SAVED = [1, 3, 5]  # ASSUMPTION: triage minutes saved per request; to be measured in shadow mode
ENC = tiktoken.get_encoding("o200k_base")


def count_messages(messages: list[dict]) -> int:
    """OpenAI chat format: about 3 tokens per message plus 3 to start the reply (an approximation)."""
    return sum(3 + len(ENC.encode(m["content"])) for m in messages) + 3


SCHEMA = {"understand": len(ENC.encode(json.dumps(strict_schema(Understanding)))),
          "decide": len(ENC.encode(json.dumps(strict_schema(Decision))))}
VARIABLE = ("<<DATA", "Confidential marker.", "10. user_reply:", "13. Channel")  # lines that change per request


def static_part(system: str) -> str:
    """The system prompt without the lines that change per request (markers, canary, language, channel)."""
    return "\n".join(x for x in system.splitlines() if not any(v in x for v in VARIABLE))


def common_prefix(texts: list[str]) -> str:
    first, last = min(texts), max(texts)
    i = 0
    while i < min(len(first), len(last)) and first[i] == last[i]:
        i += 1
    return first[:i]


def read_calls() -> list[dict]:
    rows = []
    for f in sorted(CALLS.glob("*.jsonl*")):
        opener = gzip.open if f.suffix == ".gz" else open
        with opener(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                c = json.loads(line)
                system = c["messages"][0]["content"]
                step = "understand" if system.startswith("You are the intake step") else "decide"
                rows.append({"file": f.name.split(".")[0], "step": step, "messages": len(c["messages"]), "system": system,
                             "qwen_in": c["usage"]["prompt_tokens"], "qwen_out": c["usage"]["completion_tokens"],
                             # Learn: the structured-output schema is added as a prefix to the system message
                             "gpt_in": count_messages(c["messages"]) + SCHEMA[step], "gpt_out": len(ENC.encode(c["reply"])),
                             "gpt_static": SCHEMA[step] + len(ENC.encode(static_part(system)))})
    return rows


def main() -> None:
    rows = read_calls()
    shared_now = {step: SCHEMA[step] + len(ENC.encode(common_prefix([r["system"] for r in rows if r["step"] == step])))
                  for step in SCHEMA}  # identical prefix with today's prompt layout
    with open(ROOT / "results" / "cost_tokens.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "system"])
        w.writeheader()
        w.writerows({k: v for k, v in r.items() if k != "system"} for r in rows)
    requests = sum(1 for r in rows if r["step"] == "understand")
    per = {k: sum(r[k] for r in rows) / requests for k in ("qwen_in", "qwen_out", "gpt_in", "gpt_out")}
    # Cacheable only if the identical prefix is at least 1,024 tokens (Learn: prompt caching).
    per["cacheable_now"] = sum(v for v in shared_now.values() if v >= 1024)
    per["cacheable_reordered"] = sum(r["gpt_static"] for r in rows if r["gpt_static"] >= 1024) / requests
    retries = sum(1 for r in rows if r["messages"] > 2)
    cost = {}
    for name, (p_in, p_cached, p_out) in PRICES.items():
        plain = (per["gpt_in"] * p_in + per["gpt_out"] * p_out) / 1e6
        cached = ((per["gpt_in"] - per["cacheable_reordered"]) * p_in + per["cacheable_reordered"] * p_cached + per["gpt_out"] * p_out) / 1e6
        cost[name] = {"per_request": plain, "per_request_cached_prefix": cached,
                      **{f"month_{v}": plain * v for v in VOLUMES}, **{f"month_{v}_cached": cached * v for v in VOLUMES}}
    summary = {"requests": requests, "calls": len(rows), "calls_with_retry": retries, "per_request": per,
               "schema_tokens": SCHEMA, "shared_prefix_now": shared_now, "prices_checked": CHECKED, "price_source": SOURCE,
               "cost": cost, "sources": sorted({r["file"] for r in rows})}
    (ROOT / "results" / "cost_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_doc(summary)
    print(f"{requests} requests, {len(rows)} calls -> results/cost_summary.json, docs/cost_model.md")


def write_doc(s: dict) -> None:
    p, c = s["per_request"], s["cost"]
    money = lambda x: f"${x:,.2f}" if x >= 1 else f"${x:,.4f}"
    lines = [
        "# Cost model", "",
        "Generated by `python -m eval.cost` from the prompts and replies that B3 really sent and received "
        f"({s['requests']} requests, {s['calls']} model calls in `results/llm_calls/`: {', '.join(s['sources'])}).", "",
        "**This prototype was not run against a live Azure deployment.** The token counts below are estimates: the local model "
        "uses the Qwen tokenizer, so every prompt and reply was recounted with the GPT tokenizer `o200k_base` (tiktoken). "
        "Both counts are shown.", "",
        "## Tokens per request (B3: understand + decide)", "",
        "| Count | Input | Output |", "|---|---|---|",
        f"| Local model (Qwen tokenizer, from vLLM usage) | {p['qwen_in']:,.0f} | {p['qwen_out']:,.0f} |",
        f"| Azure estimate (o200k_base: messages ≈ 3 tokens each + 3, plus the JSON schema) | {p['gpt_in']:,.0f} | {p['gpt_out']:,.0f} |", "",
        f"- The Azure estimate includes the JSON schema of each call ({s['schema_tokens']['understand']:,} + {s['schema_tokens']['decide']:,} tokens), "
        "because the structured-output schema is added as a prefix to the system message (Microsoft Learn, prompt caching, "
        "https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching, page date 2026-09-09, checked 2026-11-24).",
        f"- Calls that needed a structured-output retry: {s['calls_with_retry']} of {s['calls']}.",
        f"- **Prompt cache today: no benefit.** The cache needs an identical prefix of at least 1,024 tokens. The prompts put the "
        f"per-request random markers near the top, so the identical prefix is only {s['shared_prefix_now']['understand']:,} "
        f"(understand) and {s['shared_prefix_now']['decide']:,} (decide) tokens.",
        f"- **With a reordered prompt** (random markers, canary, language and channel moved to the end), about "
        f"{p['cacheable_reordered']:,.0f} input tokens per request become cacheable. That is a production change, not tested here.", "",
        f"## Prices (USD per 1M tokens, short context, Standard; official pricing page, checked {s['prices_checked']})", "",
        f"Source: {s['price_source']}", "",
        "| Model, deployment | Input | Cached input | Output |", "|---|---|---|---|",
        *[f"| {name} | {v[0]} | {v[1]} | {v[2]} |" for name, v in PRICES.items()], "",
        "Formula: `cost per request = input tokens × input price / 1,000,000 + output tokens × output price / 1,000,000`. "
        "In the cache columns the cacheable prefix uses the cached-input price; cache-write charges (GPT-5.6 and later) are not modeled.", "",
        "## Model cost per month", "",
        "| Model, deployment | Per request | 10,000 requests/month | 50,000 requests/month | 10,000, reordered prompt + cache | 50,000, reordered prompt + cache |",
        "|---|---|---|---|---|---|",
        *[f"| {n} | {money(v['per_request'])} | {money(v['month_10000'])} | {money(v['month_50000'])} | "
          f"{money(v['month_10000_cached'])} | {money(v['month_50000_cached'])} |" for n, v in c.items()], "",
        "A small model (Luna) for all traffic is the floor. A realistic mix sends hard cases to a larger model or uses the model "
        "router; the cost then sits between the two rows. Retries, long context and Provisioned Throughput are not modeled.", "",
        "## Staff time (assumption, not measured)", "",
        "**Assumption:** the agent saves the desk some minutes of triage per request (reading, classifying, routing, asking for "
        "missing facts), because a person only reviews the proposal. The real number must come from shadow mode.", "",
        "| Minutes saved per request (assumed) | 10,000 requests/month | 50,000 requests/month |", "|---|---|---|",
        *[f"| {m} | {m * 10_000 / 60:,.0f} hours | {m * 50_000 / 60:,.0f} hours |" for m in MINUTES_SAVED], "",
        "Even the smallest assumption (1 minute) is about 167 staff hours per month at 10,000 requests. Whether that outweighs the "
        "model cost depends on the staff cost, which this exercise does not give; make that comparison with the service owner's numbers.",
    ]
    (ROOT / "docs" / "cost_model.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
