"""B0: the agent without a model.
Keyword understanding and rule-based decisions from routing.yaml, with template replies.
It answers "how far do we get without AI?". It is also the floor for G10: a request with injected text
may not be handled more loosely than these rules handle the same text without the injected part.
"""
from __future__ import annotations

import re

from .correlate import found, has, symptoms
from .data import policies, routing
from .models import Correlation, Decision, Understanding
from .retrieve import tokens
from .sanitize import detect_signals


def language(text: str) -> str:
    return "zh" if re.search(r"[一-鿿]", text) else "en"


def hits(text: str, words: dict | list) -> int:
    words = words.get("en", []) + words.get("zh", []) if isinstance(words, dict) else words
    return sum(1 for w in words if has(text.lower(), w))


def guess_category(text: str, signals: list[str]) -> str:
    if set(signals) & set(policies()["escalate_on"]):
        return "Security"
    scores = {c: hits(text, v["keywords"]) for c, v in routing()["categories"].items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "none"


def variant(category: str, text: str) -> str:
    variants = routing()["categories"].get(category, {}).get("variants", {})
    return next((name for name, v in variants.items() if hits(text, v["when"])), "")


def required_fields(category: str, var: str = "") -> list[str]:
    cat = routing()["categories"].get(category, {})
    return list(cat.get("variants", {}).get(var, {}).get("required_fields") or cat.get("required_fields", []))


def condition(name: str, text: str, signals: list[str], u: Understanding, corr: Correlation) -> bool:
    sig = routing()["signals"]
    multi = u.impact_scope == "multiple" or hits(text, sig["multi_user"]) > 0
    checks = {
        "security_signal": lambda: bool(set(signals + u.risk_signals) & set(policies()["escalate_on"])),
        "safety_hazard": lambda: hits(text, sig["safety_hazard"]) > 0,
        "wide_outage": lambda: multi and hits(text, sig["wide_outage"]) > 0,
        "multi_user": lambda: multi,
        "multi_user_no_incident": lambda: multi and corr.status == "none",
        "blocks_critical_work": lambda: hits(text, sig["blocks_critical_work"]) > 0,
        "no_work_impact": lambda: hits(text, sig["no_work_impact"]) > 0,
    }
    return checks[name]()


def route(category: str, var: str, text: str, signals: list[str], u: Understanding, corr: Correlation) -> tuple[str, str]:
    team = routing()["categories"].get(category, {}).get("team", "none")
    for ex in routing()["team_exceptions"]:
        if ex["category"] == category and ex.get("variant", var) == var and condition(ex["if"], text, signals, u, corr):
            return ex.get("category_to", category), ex["team"]
    return category, team


def priority(text: str, signals: list[str], u: Understanding, corr: Correlation) -> str:
    for rule in routing()["priority_rules"]:
        if "if" not in rule or condition(rule["if"], text, signals, u, corr):
            return rule["priority"]
    return "P3"


def understand_offline(text: str) -> Understanding:
    cfg, low = routing()["incidents"], text.lower()
    signals = detect_signals(text)
    multi = hits(text, routing()["signals"]["multi_user"]) > 0
    first_person = re.search(r"\b(i|my|me)\b|我", low) is not None
    groups = routing()["incidents"]["symptoms"]
    return Understanding(
        intent="", service=next(iter(sorted(found(low, cfg["services"]))), ""), category_guess=guess_category(text, signals),
        symptoms=[groups[i][0] for i in sorted(symptoms(low))],
        impact_scope="multiple" if multi else ("single" if first_person else "unknown"), requested_action="",
        systems=[], folders=[], devices=[], locations=sorted(found(low, cfg["locations"]) | found(low, cfg["assets"])),
        vdi_pools=[], risk_signals=signals, missing_info=[], search_keywords=tokens(text)[:12], language=language(text))


def reply(key: str, lang: str, **values) -> str:
    return routing()["replies"][key][lang].format(**values)


def decide_offline(text: str, u: Understanding, corr: Correlation, kb_hits: list[dict]) -> Decision:
    lang, signals = u.language, u.risk_signals
    category = u.category_guess
    var = variant(category, text)
    category, team = route(category, var, text, signals, u, corr)
    prio = priority(text, signals, u, corr)
    own = routing()["categories"].get(category, {}).get("kb", "")
    ids = [h["id"] for h in kb_hits]
    kb = ([own] if own in ids else []) + [k for k in ids if k != own][:1]  # the routed category's KB first
    d = Decision(action="create_ticket", category=category, priority=prio, team=team, incident_id="",
                 approval_required=False, approver="", ticket_status="new", ticket_fields=[], missing_fields=[],
                 user_reply="", agent_note="B0 rules", cited_kb=kb, confidence=0.5)
    g = policies()["rules"]
    if category == "Security":
        d.action, d.team, d.priority = "escalate_security", "Security Operations", "P1"
        d.user_reply = g["G4"]["text"][lang]
    elif corr.status == "confirmed":
        inc = corr.incident
        d.action, d.incident_id, d.priority = "link_incident", corr.incident_id, inc["priority"]
        d.user_reply = g["G5"]["link_text"][lang].format(incident_id=corr.incident_id, summary=inc["summary"], status=inc["status"])
    elif corr.status == "possible":
        inc = corr.incident
        d.action, d.incident_id = "ask_clarifying", corr.incident_id
        d.user_reply = g["G5"]["ask_text"][corr.missing[0]][lang].format(
            incident_id=corr.incident_id, summary=inc["summary"], scope=inc["scope"])
    elif category == "none":
        oos = routing()["out_of_scope"]
        if hits(text, oos) > 0:
            d.action, d.priority, d.team, d.cited_kb = "out_of_scope", "none", "none", []
            d.user_reply = g["G12"]["text"][lang]
        else:
            d.action, d.user_reply = "ask_clarifying", reply("ask_generic", lang)
    else:
        var_cfg = routing()["categories"][category].get("variants", {}).get(var, {})
        approver = var_cfg.get("approver") or routing()["approvals"].get(category, "")
        d.approval_required, d.approver = bool(approver), approver
        d.missing_fields = required_fields(category, var)
        multi = condition("multi_user_no_incident", text, signals, u, corr)
        parts = [reply("incident_ticket" if multi else "create_ticket", lang, category=category, team=team)]
        if approver:
            parts.append(reply("needs_approval", lang, approver=approver))
        parts.append(reply("missing", lang, missing=", ".join(f.replace("_", " ") for f in d.missing_fields)))
        d.ticket_status = "pending_user"
        d.user_reply = " ".join(parts)
    if kb and d.action != "out_of_scope":
        d.user_reply += " " + reply("reference", lang, kb=", ".join(kb))
    return d
