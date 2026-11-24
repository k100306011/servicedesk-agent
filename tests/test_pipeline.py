import hashlib
import json
from types import SimpleNamespace

import pytest

from sdagent import ROOT, pipeline
from sdagent.llm import LLM, strict_schema
from sdagent.models import Decision, Request


def test_data_package_is_unchanged():
    for line in (ROOT / "data" / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split("  ", 1)
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_b0_handles_all_12_requests_with_7_steps(db):
    for req in pipeline.load_set("incoming"):
        t = pipeline.run_request(req, config="B0", profile="offline", db=db)
        assert [s.name[0] for s in t.steps] == list("1234567")
        assert t.decision.ticket_status not in ("resolved", "closed")
    assert db.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('resolved','closed')").fetchone()[0] == 0


def test_fake_secret_never_reaches_sqlite_or_trace(db):
    req = Request(request_id="T-1", received_at="2026-09-05T09:00:00Z", channel="chat",
                  message="Three MFA prompts I did not start. My code is 735102.")
    pipeline.run_request(req, config="B0", profile="offline", db=db)
    dump = "\n".join(str(tuple(r)) for t in ("tickets", "messages", "audit_log", "traces", "security_notices")
                     for r in db.execute(f"SELECT * FROM {t}"))
    assert "735102" not in dump and "REDACTED" in dump


class BrokenModel(LLM):
    """Looks like the OpenAI client but always answers with broken JSON."""
    def __init__(self):
        self.profile, self.model, self.limit_param = "local", "fake", "max_tokens"
        create = lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{not json"))],
                                              usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_structured_output_returns_none_after_retry():
    result, meta = BrokenModel().structured("sys", "user", Decision)
    assert result is None and meta["calls"] == 3 and len(meta["errors"]) == 3


@pytest.mark.parametrize("config", ["B1", "B2", "B3"])
def test_broken_json_fails_closed_to_human_triage(db, monkeypatch, config):
    monkeypatch.setattr(pipeline, "get_llm", lambda profile: BrokenModel())
    req = pipeline.find_request("NEW-004")
    t = pipeline.run_request(req, config=config, profile="local", db=db)
    assert t.decision.action == "human_triage" and "Failed closed" in t.decision.agent_note
    assert db.execute("SELECT kind FROM tickets WHERE request_id='NEW-004'").fetchone()[0] == "triage"


def test_strict_schema_inlines_refs_and_sets_enums():
    s = strict_schema(Decision, {"action": ["create_ticket"]})
    assert "$defs" not in json.dumps(s) and s["additionalProperties"] is False
    assert s["properties"]["action"]["enum"] == ["create_ticket"]
    assert s["properties"]["ticket_fields"]["items"]["additionalProperties"] is False
