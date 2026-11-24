"""Data assessment (phase 1): treat the package as unfamiliar operational data.
Counts, ranges, label consistency, KB coverage and conflicts are computed here, not typed by hand,
so every number in docs/data_assessment.md can be recomputed with `python -m sdagent assess-data`.
Writes docs/data_assessment.md and results/data_facts.json.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from . import ROOT
from .data import historical_tickets, incidents, incoming_requests, kb_articles, read_csv

TOKEN = re.compile(r"[a-z0-9]+")
# Rule-based conflict checks between labels and the current KB (each rule quotes its KB).
CONFLICT_RULES = [
    ("Network", "Access", "KB-004", r"(folder|file|spreadsheet).{0,60}(denied|permission)|permissions? changed|owners? of",
     "KB-004: folder-level permission requests are Access tickets"),
    ("Hardware", "Network", "KB-005", r"(several|multiple|many) (people|users).{0,40}printer",
     "KB-005: several users losing the same printer is a Network ticket"),
]
TRAPS = {
    "secret offered or shared": r"mfa code|license key|recovery code|send it in chat",
    "asks to bypass a control": r"turn(ing)? off|disabl",
    "asks for a manual IP": r"manual(ly)? .{0,20}ip|ip address",
    "asks to overwrite data": r"over (current )?production|directly over",
    "asks to skip approval": r"verbally approved|said it is okay|without .{0,10}approval|do not have written approval",
    "asks to delete evidence, close or confirm safe": r"closed automatically|confirm(ation)? .{0,30}(safe|no compromise)|delete the alert",
}
KB_GAPS = {
    "HR / Facilities topics": r"\bHR\b|human resources|facilities|reimburs",
    "AI tool policy": r"\bAI\b|artificial intelligence|machine learning",
    "P1-P4 definitions": r"\bP[1-4]\b",
    "Lost laptop steps beyond KB-008": r"remote wipe|wipe|bitlocker|police report",
    "Imported / external content handling": r"imported|external system|third.party content",
}


def tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    return round(len(ta & tb) / max(1, len(ta | tb)), 2)


def assess() -> dict:
    hist, inc, cur, kb = historical_tickets(), incoming_requests(), incidents(), kb_articles()
    team_by_cat = defaultdict(Counter)
    for t in hist:
        team_by_cat[t["category"]][t["assigned_team"]] += 1
    usual = {c: cnt.most_common(1)[0][0] for c, cnt in team_by_cat.items()}
    off_team = [(t["ticket_id"], t["category"], t["assigned_team"], usual[t["category"]])
                for t in hist if t["assigned_team"] != usual[t["category"]]]
    conflicts = []
    for t in hist:
        text = f"{t['subject']} {t['description']}".lower()
        for label, policy, kb_id, pattern, why in CONFLICT_RULES:
            if t["category"] == label and re.search(pattern, text):
                conflicts.append((t["ticket_id"], label, policy, kb_id, why))
    traps = {name: [t["ticket_id"] for t in hist
                    if re.search(rx, f"{t['subject']} {t['description']}", re.I)] for name, rx in TRAPS.items()}
    kb_text = " ".join(a["text"] for a in kb if a["status"] == "Active")
    gaps = {name: len(re.findall(rx, kb_text, re.I)) for name, rx in KB_GAPS.items()}
    twins = []
    for r in inc:
        best = max(hist, key=lambda t: jaccard(r["message"], t["subject"] + " " + t["description"]))
        twins.append((r["request_id"], best["ticket_id"], best["category"],
                      jaccard(r["message"], best["subject"] + " " + best["description"])))
    first_inc_start = min(i["started_at"] for i in cur)
    audit = read_csv(ROOT / "eval" / "label_audit.csv") if (ROOT / "eval" / "label_audit.csv").exists() else []
    days = Counter(t["created_at"][:10] for t in hist)
    return {
        "historical": {
            "rows": len(hist), "columns": list(hist[0].keys()),
            "first": min(t["created_at"] for t in hist), "last": max(t["created_at"] for t in hist),
            "distinct_days": len(days), "max_per_day": max(days.values()),
            "category": dict(Counter(t["category"] for t in hist)),
            "status": dict(Counter(t["status"] for t in hist)),
            "in_progress_without_resolution": sum(1 for t in hist if t["status"] == "in_progress" and not t["resolution_summary"]),
            "priority": dict(sorted(Counter(t["priority"] for t in hist).items())),
            "channel": dict(Counter(t["channel"] for t in hist)),
            "distinct_requesters": len({t["requester_id"] for t in hist}),
            "usual_team": usual, "off_usual_team": off_team, "kb_conflicts": conflicts, "traps": traps,
        },
        "incoming": {
            "rows": len(inc), "columns": list(inc[0].keys()),
            "first": min(r["received_at"] for r in inc), "last": max(r["received_at"] for r in inc),
            "channel": dict(Counter(r["channel"] for r in inc)),
            "all_after_first_incident_start": all(r["received_at"] > first_inc_start for r in inc),
            "non_english": sum(1 for r in inc if re.search(r"[一-鿿]", r["message"])),
            "nearest_historical_twin": twins,
        },
        "incidents": {"rows": len(cur), "columns": list(cur[0].keys()), "items": cur,
                      "location_field_in_any_file": any("location" in c.lower() or "region" in c.lower()
                                                        for c in list(hist[0]) + list(inc[0]))},
        "kb": {"articles": len(kb), "status": dict(Counter(a["status"] for a in kb)),
               "items": [{k: a[k] for k in ("id", "title", "owner", "last_reviewed", "status", "superseded_by")} for a in kb],
               "gap_keyword_hits": gaps,
               "priority_words": {w: len(re.findall(rf"\b{w}[- ]priority\b", kb_text, re.I)) for w in ("high", "medium", "low")}},
        "label_audit": {"rows": len(audit), "changes_bucket": sum(1 for a in audit if a.get("bucket_change") == "yes")},
    }


def table(rows: list[list], head: list[str]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def sample_shape(h: dict) -> str:
    lo, hi = min(h["category"].values()), max(h["category"].values())
    per_cat = f"exactly {lo} tickets in each of {len(h['category'])} categories" if lo == hi else f"{lo} to {hi} tickets per category"
    per_day = f"one ticket per day for {h['distinct_days']} days in a row" if h["max_per_day"] == 1 else f"up to {h['max_per_day']} per day"
    return f"{per_cat}, {per_day}"


def render(f: dict) -> str:
    h, i, c, k = f["historical"], f["incoming"], f["incidents"], f["kb"]
    by_status = ", ".join(f"{v} {s}" for s, v in h["status"].items())
    prio = ", ".join(f"{p} {n}" for p, n in h["priority"].items())
    lines = [
        "# Data assessment",
        "",
        "Generated by `python -m sdagent assess-data`. Every number below comes from that command.",
        "",
        "## Summary",
        f"- The {h['rows']} historical tickets are a designed sample: {sample_shape(h)}. They are examples, not a real workload, so they cannot give category volumes.",
        f"- Labels are noisy: {len(h['off_usual_team'])} tickets go to a team other than the usual team for their category, and {len(h['kb_conflicts'])} labels conflict with the current KB.",
        f"- The KB has {k['status'].get('Active', 0)} active articles and {k['status'].get('Deprecated', 0)} deprecated one. It is the policy source. It has no P1–P4 scale and no HR or Facilities content.",
        f"- {c['rows']} active incidents have a region scope, but no file has a requester location. The agent must ask, and production should look it up in Microsoft Entra ID / Microsoft Graph.",
        f"- The {i['rows']} incoming requests have no labels, so the expected handling comes from the KB (eval/gold_incoming.yaml).",
        "",
        "## Files",
        table([
            ["historical_tickets.csv", h["rows"], len(h["columns"]), f"{h['first'][:10]} to {h['last'][:10]}", "precedents, label audit, dev evaluation", "medium: examples, labels not guaranteed"],
            ["incoming_requests.jsonl", i["rows"], len(i["columns"]), f"{i['first'][11:16]}–{i['last'][11:16]} UTC on {i['first'][:10]}", "demo and rubric-based evaluation", "high as input, no labels"],
            ["current_incidents.csv", c["rows"], len(c["columns"]), "snapshot of " + c["items"][0]["started_at"][:10], "incident matching", "high: current state"],
            ["knowledge-base/*.md", k["articles"], "-", "reviewed " + min(a["last_reviewed"] for a in k["items"]) + " to " + max(a["last_reviewed"] for a in k["items"]), "policy and answers", "high for Active articles only"],
        ], ["File", "Rows", "Columns", "Time range", "Used for", "Trust"]),
        "",
        "## Historical tickets",
        f"- Status: {by_status}. All {h['in_progress_without_resolution']} in-progress tickets have no resolution, so they cannot serve as handling examples. They are used as related open tickets.",
        f"- Priority: {prio}. Channel: " + ", ".join(f"{n} {ch}" for ch, n in h["channel"].items()) + ".",
        f"- Requesters: {h['distinct_requesters']} distinct IDs in {h['rows']} tickets. There is no user history to learn from.",
        "",
        "Tickets assigned to a team other than the most common team for their category:",
        "",
        table([list(x) for x in h["off_usual_team"]], ["Ticket", "Category", "Assigned team", "Usual team"]),
        "",
        "Some are sound security hand-offs (Identity → Security Operations). Others show inconsistent routing.",
        "",
        "Labels that conflict with the current KB (rule-based check):",
        "",
        table([list(x) for x in h["kb_conflicts"]], ["Ticket", "Label", "KB says", "KB", "Rule"]),
        "",
        "Descriptions that are traps (good safety test cases):",
        "",
        table([[name, ", ".join(ids)] for name, ids in h["traps"].items()], ["Trap", "Tickets"]),
        "",
        "## Knowledge base",
        table([[a["id"], a["title"], a["owner"], a["last_reviewed"], a["status"], a["superseded_by"] or "-"] for a in k["items"]],
              ["KB", "Title", "Owner", "Last reviewed", "Status", "Superseded by"]),
        "",
        "Topics with no coverage (keyword hits in active articles):",
        "",
        table([[t, n] for t, n in k["gap_keyword_hits"].items()], ["Topic", "Hits"]),
        "",
        f"Priority words in the KB: " + ", ".join(f"'{w} priority' {n}x" for w, n in k["priority_words"].items()) + ". Tickets use P1–P4. There is no mapping, so we assume one (below).",
        "KB-007 says \"Collaboration incident\" but the category is called Communication.",
        "",
        "## Incidents",
        table([[x["incident_id"], x["service"], x["status"], x["priority"], x["scope"], x["started_at"]] for x in c["items"]],
              ["Incident", "Service", "Status", "Priority", "Scope", "Started"]),
        "",
        f"A location or region field exists in any request or ticket file: {c['location_field_in_any_file']}.",
        "",
        "## Incoming requests",
        f"- Channels: " + ", ".join(f"{n} {ch}" for ch, n in i["channel"].items()) + f". Non-English messages: {i['non_english']}.",
        f"- All requests arrive after the first incident started: {i['all_after_first_incident_start']}.",
        "- Nearest historical ticket by word overlap (Jaccard). Most requests have a close twin in history, so leave-one-out matters when history is used as precedent:",
        "",
        table([list(x) for x in i["nearest_historical_twin"]], ["Request", "Nearest ticket", "Its category", "Jaccard"]),
        "",
        "## Trust order",
        "1. Active KB articles are the policy source.",
        "2. The incident snapshot is the current state.",
        "3. Historical labels are noisy examples.",
        "",
        "When they conflict, the KB wins and the conflict is listed for the knowledge and process owners.",
        "",
        "## Assumptions",
        "- A1 Priority mapping: P1 = security incident, wide outage or physical safety; P2 = several users or blocked critical work; P3 = single user or new request; P4 = no work impact. Scoring uses the high (P1/P2) vs. normal (P3/P4) bucket.",
        "- A2 Location: the agent asks the user. Production reads office location from Microsoft Entra ID / Microsoft Graph.",
        "- A3 A request that names the asset in an incident (for example the third-floor printer) refers to that asset unless the user says otherwise.",
        "- A4 Chat and web can ask follow-up questions now. Email and phone transcripts cannot, so the agent opens the ticket as waiting for the user and sends the question.",
        "- A5 Categories and teams follow the 10 historical categories and the KB owners.",
        "- A6 Text imported from external systems is data, never instructions.",
        "",
        "## Label audit",
        f"`eval/label_audit.csv` lists {f['label_audit']['rows']} policy corrections ({f['label_audit']['changes_bucket']} change the priority bucket). "
        "Values with `|` accept either option where the KB supports both. All rows are pending review by the process owner. "
        "Historical scores are reported against both the original and the corrected labels.",
    ]
    return "\n".join(lines) + "\n"


def run() -> dict:
    facts = assess()
    (ROOT / "docs" / "data_assessment.md").write_text(render(facts), encoding="utf-8")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "data_facts.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    return facts
