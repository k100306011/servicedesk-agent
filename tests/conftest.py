import pytest

from sdagent import actions
from sdagent.models import Correlation, Decision


def make_decision(**over) -> Decision:
    base = dict(action="create_ticket", category="Access", priority="P3", team="Identity and Access Management",
                incident_id="", approval_required=False, approver="", ticket_status="new", ticket_fields=[],
                missing_fields=[], user_reply="", agent_note="", cited_kb=[], confidence=0.8)
    base.update(over)
    return Decision(**base)


def incident(i: str) -> dict:
    from sdagent.data import incidents
    return next(x for x in incidents() if x["incident_id"] == i)


def corr(status: str = "none", incident_id: str = "", missing: list | None = None) -> Correlation:
    return Correlation(status=status, incident_id=incident_id, incident=incident(incident_id) if incident_id else {},
                       missing=missing or [])


@pytest.fixture
def db(tmp_path):
    conn = actions.connect(tmp_path / "test.db")
    yield conn
    conn.close()
