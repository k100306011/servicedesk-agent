from eval import report


def item(item_id: str, negated: list[str] | None = None) -> dict:
    return {"item": item_id, "channel": "chat", "message": "m", "guard_fixes": [],
            "decision": {"action": "create_ticket", "category": "Access", "priority": "P3",
                         "team": "Identity and Access Management", "incident_id": "", "user_reply": "r"},
            "checks": {"human": [], "negated": negated or []}}


def test_human_review_keeps_the_reviewer_scores(tmp_path, monkeypatch):
    (tmp_path / "eval").mkdir()
    scores = tmp_path / "eval" / "human_scores.csv"
    scores.write_text("tag,set,item,check,kind,score,verdict,note\n"
                      "dev,incoming,NEW-001,,reply,4,,Names only the manager.\n"
                      "final,holdout,NEW-002-A,asks_for_secret,negated,,ok,Tells the user not to share the code.\n",
                      encoding="utf-8")
    monkeypatch.setattr(report, "ROOT", tmp_path)
    monkeypatch.setattr(report, "HUMAN", scores)
    data = {("dev", "B3", "incoming", "local"): [[item("NEW-001")]],
            ("final", "B3", "holdout", "local"): [[item("NEW-002-A", ["asks_for_secret: Please do not share your MFA code."])]]}

    summary = report.human_review(data, "dev")
    text = (tmp_path / "eval" / "human_review.md").read_text(encoding="utf-8")

    assert "- Score (1–5): 4" in text and "- Notes: Names only the manager." in text
    assert "→ reviewer: ok (Tells the user not to share the code.)" in text
    assert "1 of 1 scored, mean 4.0" in summary[0]
    assert "1 of 1 reviewed, 0 counted as violations" in summary[1]
