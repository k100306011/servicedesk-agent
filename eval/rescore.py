"""Recompute the checks of existing result files with the current eval/checks.py.
Used after a logged checker fix (eval/rubric_changes.md). secret_redacted needs the database of the run,
so its stored value is kept as it was. Usage: python -m eval.rescore [tag ...]
"""
import json
import sys

from eval.checks import check_item
from eval.report import RUNS
from eval.run_eval import load_gold
from sdagent.models import ACTIONS


def main(tags: list[str]) -> None:
    gold, changed = load_gold(), 0
    for f in sorted(RUNS.glob("*.jsonl")):
        if tags and f.name.split("__")[0] not in tags:
            continue
        lines = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        for r in lines[1:]:
            old = r["checks"]
            r["stored_text"] = ""
            new = check_item(r, gold.get(r["item"]) or {"action": ACTIONS})
            if "secret_redacted" in old["critical"]:
                new["critical"]["secret_redacted"] = old["critical"]["secret_redacted"]
                new["quality"]["secret_redacted"] = not old["critical"]["secret_redacted"] if "secret_redacted" in new["quality"] else None
                new["quality"] = {k: v for k, v in new["quality"].items() if v is not None}
            del r["stored_text"]
            changed += new != old
            r["checks"] = new
        f.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    print(f"rescored; {changed} item results changed")


if __name__ == "__main__":
    main(sys.argv[1:])
