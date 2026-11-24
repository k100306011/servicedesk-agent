from sdagent.correlate import correlate
from sdagent.data import incoming_requests
from sdagent.retrieve import kb_index, retrieve, search_kb, search_precedents

REQ = {r["request_id"]: r for r in incoming_requests()}


def run(rid: str):
    r = REQ[rid]
    return correlate(r["message"], r["received_at"])


def test_new_005_confirms_maj_303():
    c = run("NEW-005")
    assert (c.status, c.incident_id, c.missing) == ("confirmed", "MAJ-303", [])


def test_new_010_is_possible_maj_302_needs_pool():
    c = run("NEW-010")
    assert (c.status, c.incident_id, c.missing) == ("possible", "MAJ-302", ["pool_or_region"])
    assert "INC-1046" in c.related_tickets


def test_new_007_matches_maj_301_but_location_is_missing():
    c = run("NEW-007")
    assert (c.status, c.incident_id, c.missing) == ("possible", "MAJ-301", ["location"])


def test_location_confirms_or_excludes():
    assert correlate("我們部門都寄不出信，我們在新加坡辦公室", "2026-09-05T09:00:00Z").status == "confirmed"
    assert correlate("Nobody can send email from the New York office", "2026-09-05T09:00:00Z").status == "none"


def test_old_request_does_not_match_current_incident():
    assert correlate("Nobody in the department can send email", "2026-08-03T09:00:00Z").status == "none"


def test_deprecated_kb_011_is_never_indexed_or_returned():
    _, docs = kb_index()
    assert "KB-011" not in {d["id"] for d in docs}
    for q in ["LegacyConnect installer", "import gateway certificate legacy VPN client", "KB-011 reinstall LegacyConnect"]:
        assert "KB-011" not in {h["id"] for h in search_kb(q, k=12, min_score=0)}
    assert "KB-011" not in {h["id"] for h in retrieve("legacy vpn", default_kb="KB-011")["kb"]}


def test_out_of_scope_question_has_no_kb():
    assert search_kb("Does the company reimburse ergonomic chairs for home offices?") == []


def test_precedents_leave_one_out():
    hits = search_precedents("Mapped drive shows permission denied Legal folder", exclude="INC-1016")
    assert "INC-1016" not in [h["id"] for h in hits]
