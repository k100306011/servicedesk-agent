"""Step 3: correlate with active incidents (KB-012).
Every request is checked; the model never decides whether to check. KB-012 gives four criteria:
service, symptom, location and time window. Result: confirmed (all four), possible (location missing,
so ask first) or none. Open historical tickets with the same service and symptom are "related tickets", not incidents.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from .data import historical_tickets, incidents, routing
from .models import Correlation, Understanding


def has(text: str, word: str) -> bool:
    if re.search(r"[一-鿿]", word):
        return word in text
    return re.search(rf"(?<![a-z0-9]){re.escape(word.lower())}(?![a-z0-9])", text) is not None


def found(text: str, table: dict) -> set[str]:
    return {key for key, words in table.items() if any(has(text, w) for w in words)}


def symptoms(text: str) -> set[int]:
    return {i for i, group in enumerate(routing()["incidents"]["symptoms"]) if any(has(text, w) for w in group)}


def profile(inc: dict) -> dict:
    cfg = routing()["incidents"]
    text = f"{inc['service']} {inc['summary']}".lower()
    return {"services": found(text, cfg["services"]), "symptoms": symptoms(text), "assets": found(text, cfg["assets"]),
            "scope": {s.strip().upper() for s in inc["scope"].split(";")}}


def when(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def match(text: str, received_at: str, inc: dict) -> tuple[list[str], list[str]] | None:
    """Return (matched, missing) criteria, or None when the incident does not match."""
    cfg, p = routing()["incidents"], profile(inc)
    if inc["status"].lower() not in cfg["active_statuses"]:
        return None
    if not (found(text, cfg["services"]) & p["services"]) or not (symptoms(text) & p["symptoms"]):
        return None
    start = when(inc["started_at"])
    if not (start - timedelta(hours=cfg["window_hours_before"]) <= when(received_at)
            <= start + timedelta(hours=cfg["window_hours_after"])):
        return None
    matched = ["service", "symptom", "time window"]
    regions = found(text, cfg["locations"])
    if regions & p["scope"]:
        return matched + ["location"], []
    if found(text, cfg["assets"]) & p["assets"]:
        return matched + ["location (named asset)"], []
    if regions:  # the user is somewhere else: this incident does not cover them
        return None
    return matched, ["pool_or_region" if "VDI" in p["services"] else "location"]


def related_open(text: str, exclude: str = "") -> list[str]:
    cfg = routing()["incidents"]
    out = []
    for t in historical_tickets():
        if t["status"] != "in_progress" or t["ticket_id"] == exclude:
            continue
        other = f"{t['subject']} {t['description']}".lower()
        if found(text, cfg["services"]) & found(other, cfg["services"]) and symptoms(text) & symptoms(other):
            out.append(t["ticket_id"])
    return out


def correlate(text: str, received_at: str, u: Understanding | None = None, exclude: str = "") -> Correlation:
    """text is the sanitized request; the model's reading (service, symptoms, locations...) is added to it."""
    if u is not None:
        text = " ".join([text, u.service, *u.symptoms, *u.locations, *u.vdi_pools, *u.devices, *u.search_keywords])
    text = text.lower()
    best = Correlation(related_tickets=related_open(text, exclude))
    for inc in incidents():
        result = match(text, received_at, inc)
        if result is None:
            continue
        matched, missing = result
        status = "possible" if missing else "confirmed"
        if best.status == "none" or (best.status == "possible" and status == "confirmed"):
            best = Correlation(status=status, incident_id=inc["incident_id"], incident=inc, matched=matched,
                               missing=missing, related_tickets=best.related_tickets)
    return best
