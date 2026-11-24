"""Switch check: the azure profile against an OpenAI-compatible local server gives the same result as the local profile.
python -m eval.azure_switch [base_url]   (default http://127.0.0.1:18100/v1/)
This proves that switching is a configuration change only. It does NOT measure Azure: no live Azure deployment was used.
Writes results/azure_switch_check.json and results/azure_switch_check.md.
"""
import json
import os
import sys

from sdagent import ROOT, actions, pipeline

ITEMS = ["NEW-005", "NEW-009", "NEW-012"]
DECISION = ["action", "category", "priority", "team", "incident_id", "approval_required", "approver", "ticket_status", "cited_kb"]
TEXT = ["user_reply", "missing_fields"]  # model-written text; varies run to run because canary and markers are random


def main(base_url: str = "http://127.0.0.1:18100/v1/") -> None:
    os.environ.update({"AZURE_OPENAI_BASE_URL": base_url, "AZURE_OPENAI_API_KEY": "local-test-key",
                       "AZURE_OPENAI_DEPLOYMENT": os.getenv("LOCAL_MODEL", "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ")})
    db = actions.connect(":memory:")
    rows = []
    for item in ITEMS:
        run = lambda profile: pipeline.run_request(pipeline.find_request(item), config="B3", profile=profile, db=db).decision.model_dump()
        out = {"local": run("local"), "azure": run("azure"), "local_again": run("local")}  # local twice = control
        same = lambda a, b, fields: all(out[a][f] == out[b][f] for f in fields)
        rows.append({"item": item, "decision_same_local_azure": same("local", "azure", DECISION),
                     "decision_same_local_local": same("local", "local_again", DECISION),
                     "text_same_local_azure": same("local", "azure", TEXT), "text_same_local_local": same("local", "local_again", TEXT),
                     "local": {f: out["local"][f] for f in DECISION[:5]}, "azure": {f: out["azure"][f] for f in DECISION[:5]}})
    result = {"base_url": base_url, "deployment": os.environ["AZURE_OPENAI_DEPLOYMENT"], "items": rows,
              "note": "Same OpenAI-compatible server behind both profiles. Proves the switch is configuration only; "
                      "it is not a measurement on Azure."}
    (ROOT / "results" / "azure_switch_check.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Azure profile switch check", "", "`python -m eval.azure_switch` runs B3 twice per item: `--profile local` and "
          "`--profile azure`, with the azure settings pointed at the same local OpenAI-compatible server. "
          "**No live Azure deployment was used**; this only shows that switching is a configuration change.", "",
          "Decision fields: " + ", ".join(DECISION) + ". Reply text and the model's list of missing fields are compared separately, "
          "with a control: the local profile run twice. The canary and the spotlighting markers are random on every request, "
          "so the prompt differs slightly on every run and the wording can change even inside one profile.", "",
          "| Item | Decision same: local vs azure | Decision same: local vs local | Text same: local vs azure | Text same: local vs local | Decision (local) | Decision (azure) |",
          "|---|---|---|---|---|---|---|"]
    yn = lambda b: "yes" if b else "no"
    for r in rows:
        md.append(f"| {r['item']} | {yn(r['decision_same_local_azure'])} | {yn(r['decision_same_local_local'])} | "
                  f"{yn(r['text_same_local_azure'])} | {yn(r['text_same_local_local'])} | "
                  f"{' / '.join(str(v) or '-' for v in r['local'].values())} | {' / '.join(str(v) or '-' for v in r['azure'].values())} |")
    (ROOT / "results" / "azure_switch_check.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main(*sys.argv[1:])
