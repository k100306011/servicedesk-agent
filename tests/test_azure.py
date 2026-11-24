"""Contract tests for the azure profile with a fake HTTP server (httpx.MockTransport).
No real Azure call is made: these tests prove the request shape, not Azure quality.
"""
import json
import logging

import httpx2 as httpx  # the HTTP client package the openai SDK uses (MockTransport fakes the server)
import pytest

from sdagent import pipeline
from sdagent.llm import LLM
from sdagent.models import Decision

BASE = "https://contoso-test.openai.azure.com/openai/v1/"
KEY = "test-key-AZURE-0123456789abcdef"
DEPLOYMENT = "triage-small-test"
UNDERSTANDING = {"intent": "printer keeps going offline", "service": "Printer", "category_guess": "Hardware",
                 "symptoms": ["offline"], "impact_scope": "multiple", "requested_action": "fix the printer", "systems": [],
                 "folders": [], "devices": ["third-floor printer"], "locations": ["third floor"], "vdi_pools": [],
                 "risk_signals": [], "missing_info": [], "search_keywords": ["printer", "offline"], "language": "en"}
DECISION = {"action": "link_incident", "category": "Hardware", "priority": "P2", "team": "Workplace Technology",
            "incident_id": "MAJ-303", "approval_required": False, "approver": "", "ticket_status": "new",
            "ticket_fields": [], "missing_fields": [], "user_reply": "This matches MAJ-303, which is being investigated.",
            "agent_note": "Linked to MAJ-303.", "cited_kb": ["KB-005"], "confidence": 0.9}


def fake_azure(seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append({"url": str(request.url), "headers": dict(request.headers), "body": body})
        name = body.get("response_format", {}).get("json_schema", {}).get("name", "")
        content = UNDERSTANDING if name == "Understanding" else DECISION
        return httpx.Response(200, json={
            "id": "chatcmpl-test", "object": "chat.completion", "created": 0, "model": DEPLOYMENT,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
    return handler


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_BASE_URL", BASE)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", KEY)
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", DEPLOYMENT)
    seen = []
    return LLM("azure", http_client=httpx.Client(transport=httpx.MockTransport(fake_azure(seen)))), seen


def test_azure_request_contract(azure):
    llm, seen = azure
    result, meta = llm.structured("system", "user", Decision)
    req = seen[0]
    assert req["url"] == BASE + "chat/completions"                       # a. v1 endpoint + chat/completions
    assert req["body"]["model"] == DEPLOYMENT                            # b. model is the deployment name
    assert req["headers"]["authorization"] == f"Bearer {KEY}"            # c. the key is sent
    assert isinstance(result, Decision) and result.incident_id == "MAJ-303" and meta["calls"] == 1  # d. parsed
    assert req["body"]["response_format"]["type"] == "json_schema"
    assert "max_completion_tokens" in req["body"] and "max_tokens" not in req["body"]
    assert not {"extra_body", "guided_json", "guided_decoding_backend", "guided_choice"} & set(req["body"])


def test_azure_key_never_reaches_logs_or_traces(azure, monkeypatch, tmp_path, db, caplog, capsys):
    llm, seen = azure
    monkeypatch.setattr(pipeline, "get_llm", lambda profile: llm)
    calls = tmp_path / "calls.jsonl"
    monkeypatch.setenv("SDAGENT_LLM_LOG", str(calls))
    caplog.set_level(logging.DEBUG)
    t = pipeline.run_request(pipeline.find_request("NEW-005"), config="B3", profile="azure", db=db)
    stored = "\n".join(str(tuple(r)) for table in ("tickets", "messages", "links", "audit_log", "traces", "security_notices")
                       for r in db.execute(f"SELECT * FROM {table}"))
    out = capsys.readouterr()
    assert len(seen) == 2 and t.decision.action == "link_incident" and calls.read_text().count("\n") == 2
    for text in (stored, t.model_dump_json(), calls.read_text(), caplog.text, out.out, out.err):
        assert KEY not in text
