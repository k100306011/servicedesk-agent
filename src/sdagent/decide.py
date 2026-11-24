"""Step 5: decide with the model.
The prompt carries the full text of the retrieved KB articles, the incident check, precedents, the priority mapping
and the routing table. The action must come from a fixed list (enforced by the JSON schema).
normalize() then lists every required field the model did not fill, so ticket quality does not depend on the model.
"""
from __future__ import annotations

import json

from .baseline import required_fields, variant
from .data import routing
from .llm import LLM, render
from .models import ACTIONS, TICKET_STATUS, Correlation, Decision, Understanding
from .understand import DATA_RULE, history_text


def routing_table() -> str:
    lines = []
    for name, c in routing()["categories"].items():
        line = f"- {name} -> {c['team']}. Required fields: {', '.join(c['required_fields'])}."
        for vname, v in c.get("variants", {}).items():
            line += f" For {vname.replace('_', ' ')}: {', '.join(v['required_fields'])}."
        lines.append(f"{line} {c['note']}")
    return "\n".join(lines)


def enums() -> dict:
    r = routing()
    return {"action": ACTIONS, "category": list(r["categories"]) + ["none"], "team": r["teams"] + ["none"],
            "priority": ["P1", "P2", "P3", "P4", "none"], "ticket_status": TICKET_STATUS}


def channel_rule(channel: str) -> str:
    if channel in routing()["async_channels"]:
        return ("The user cannot answer right away. Choose the action as usual; the system opens the ticket as "
                "waiting for the user and sends your questions.")
    return "You can ask the user follow-up questions now."


def decide(llm: LLM, request: str, channel: str, canary: str, history: list[dict], u: Understanding,
           corr: Correlation, retrieved: dict, open_tag: str = "", close_tag: str = "") -> tuple[Decision | None, dict]:
    inc = corr.incident
    corr_view = {"status": corr.status, "incident_id": corr.incident_id, "matched": corr.matched, "missing": corr.missing,
                 "related_open_tickets": corr.related_tickets}
    if inc:
        corr_view.update({k: inc[k] for k in ("service", "summary", "status", "priority", "scope", "started_at")})
    kb = "\n\n".join(h["text"] for h in retrieved["kb"]) or "(no relevant KB article)"
    prec = "\n".join(f"- {p['id']} ({p['category']}, {p['team']}, {p['priority']}): {p['summary']} -> {p['resolution']}"
                     for p in retrieved["precedents"]) or "(none)"
    prio = " ".join(f"{p}: {text}." for p, text in routing()["priority"].items()) + " When you link to an incident, use its priority."
    system, user = render(
        "decide", data_rule=DATA_RULE.format(open=open_tag, close=close_tag) if open_tag else "",
        priority_rules=prio, routing_table=routing_table(), language="Chinese (Traditional, Taiwan)" if u.language == "zh" else "English",
        channel=channel, channel_rule=channel_rule(channel), canary=canary, history=history_text(history), request=request,
        understanding=u.model_dump_json(), correlation=json.dumps(corr_view, ensure_ascii=False), kb=kb, precedents=prec)
    return llm.structured(system, user, Decision, enums(), max_tokens=900)


def decide_llm_only(llm: LLM, request: str, channel: str, canary: str, history: list[dict]) -> tuple[Decision | None, dict]:
    """B1: one call, only the category and team lists. No KB, no incidents, no sanitize, no guard."""
    r = routing()
    system, user = render("llm_only", actions=", ".join(a for a in ACTIONS if a != "human_triage"),
                          categories=", ".join(r["categories"]), teams=", ".join(r["teams"]), canary=canary,
                          channel=channel, history=history_text(history), request=request)
    return llm.structured(system, user, Decision, enums(), max_tokens=900)


def normalize(d: Decision, text: str) -> Decision:
    """List every KB-required field that has no value, so a created ticket is complete or asks for the rest."""
    if d.action in ("create_ticket", "ask_clarifying", "escalate_security") and d.category in routing()["categories"]:
        filled = {f.name for f in d.ticket_fields if f.value.strip() and f.value.strip().lower() not in ("unknown", "n/a", "")}
        need = required_fields(d.category, variant(d.category, text))
        d.missing_fields = list(dict.fromkeys([m for m in d.missing_fields if m not in filled] +
                                              [f for f in need if f not in filled]))
    elif d.action in ("link_incident", "out_of_scope"):
        d.missing_fields = []
    return d
