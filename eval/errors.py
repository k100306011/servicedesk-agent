"""List every failed check for one tag and configuration, with the decision, the rubric and the guard fixes.
Usage: python -m eval.errors <tag> <config> [set]      e.g. python -m eval.errors dev B3 incoming
Each line points at the raw results file, so the full trace is one search away.
"""
import json
import sys
from collections import defaultdict

from eval.report import RUNS
from eval.run_eval import load_gold


def main(tag: str, config: str, only_set: str = "") -> None:
    gold, seen = load_gold(), defaultdict(list)
    for f in sorted(RUNS.glob(f"{tag}__{config}__*.jsonl")):
        lines = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        run = lines[0]["meta"]["run"]
        for r in lines[1:]:
            if only_set and r["set"] != only_set:
                continue
            fails = [k for k, v in r["checks"]["critical"].items() if v]
            fails += [k for k, v in r["checks"]["quality"].items() if not v]
            if r["set"] == "historical":
                fails += [k for k, v in r.get("labels", {}).items() if k.startswith("corrected") and not v]
            if fails or r["checks"]["human"]:
                seen[r["item"]].append((run, fails, r, f.name))
    for item, rows in sorted(seen.items()):
        g = gold.get(item, {})
        print(f"\n## {item}  (failed in {len(rows)} run(s))  rubric action={g.get('action')} team={g.get('team')} priority={g.get('priority')}")
        for run, fails, r, fname in rows:
            d = r["decision"]
            print(f"  run {run}: FAIL {fails} | human {r['checks']['human']}")
            print(f"    decision: {d['action']} | {d['category']} | {d['priority']} | {d['team']} | {d['incident_id']} | approver={d['approver']}")
            if r.get("pre_guard"):
                p = r["pre_guard"]
                print(f"    before guard: {p['action']} | {p['category']} | {p['priority']} | {p['team']}")
            print(f"    fixes: {[x['rule'] + ' ' + x['change'] for x in r['guard_fixes']]}")
            print(f"    reply: {d['user_reply'][:300]}")
            print(f"    file: results/runs/{fname}")


if __name__ == "__main__":
    main(*sys.argv[1:])
