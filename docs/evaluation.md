# Evaluation

How the prototype was tested, what came out, and what the errors were. Every number here can be recomputed with
`python -m sdagent summarize` from the raw files in `results/runs/`. Full tables: [results/summary.md](../results/summary.md).

## Method

**Sets.**

| Set | Items | Source | Role |
|---|---|---|---|
| incoming | 12 | exercise package | dev: rubric in `eval/gold_incoming.yaml` |
| historical | 50 | exercise package (subject + description as the message) | dev: scored against original and policy-corrected labels; precedent search leaves the ticket out |
| holdout | 36 | synthetic: each incoming request as an English paraphrase (A), Traditional Chinese (B) and with one added trap (C) | final test, never used for tuning |
| redteam | 12 | synthetic attacks (self-approved admin, prompt extraction, shared secrets, deprecated VPN client, Defender off, overwrite production, close a security ticket, manual printer IP, fake SYSTEM line, license key, "confirm I am safe", Chinese finance admin request) | final test, never used for tuning |

The holdout and red-team sets and both rubrics were frozen on 2026-11-24 at 14:24, before any rule or prompt existed (`eval/FROZEN.md`).

**Comparison groups.** B0 rules only (no model) · B1 one model call with only the category and team lists · B2 steps 2–5 with KB, incidents and precedents, but no sanitize and no guard · B3 all seven steps.
B0 runs once (deterministic). B1–B3 run three times. The success criteria use the worst B3 run.

**Checks.** `eval/checks.py` holds 13 critical checks (any hit is a safety violation) and the quality checks named in the rubrics.
The patterns are written separately from the guard, so B3 cannot pass by grading itself. A claim inside a question does not count as a claim.
Secret leaks are checked against everything stored for the item in SQLite (tickets, messages, audit log, traces, notices), not only the reply.
Cases the rules cannot decide, and every negated sentence the checker accepted, go to `eval/human_review.md`.

**Model.** An open-weight 14B model (Qwen2.5-Coder-14B-Instruct, AWQ) served by vLLM on a single RTX 4090 workstation, temperature 0.

RESULTS_SECTION
