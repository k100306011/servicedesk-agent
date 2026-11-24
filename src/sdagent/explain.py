"""Print a trace as a readable step-by-step story (python -m sdagent run --id NEW-005 --explain).
Used for the demo fallback, for debugging, and to learn how each step changed the outcome.
"""
from __future__ import annotations

import json

from .models import Trace


def compact(value, limit: int = 600) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[:limit] + " ..."


def short(t: Trace) -> str:
    d = t.decision
    lines = [f"{t.request_id} [{t.config}/{t.profile}] {d.action} | {d.category} | {d.priority} | {d.team}"
             + (f" | incident {d.incident_id}" if d.incident_id else ""),
             f"reply: {d.user_reply}", f"cited: {d.cited_kb}  tools: {[a['tool'] for a in t.actions]}  time: {t.total_ms} ms"]
    if t.guard_fixes:
        lines.append(f"guard fixes: {[f['rule'] + ': ' + f['change'] for f in t.guard_fixes]}")
    return "\n".join(lines)


def explain(t: Trace) -> str:
    out = [f"=== {t.request_id} | config {t.config} | profile {t.profile} | channel {t.channel} ===",
           f"Request (as stored): {t.message}", ""]
    for s in t.steps:
        tok = f" | tokens in/out {s.tokens.get('prompt_tokens', 0)}/{s.tokens.get('completion_tokens', 0)}" if s.tokens else ""
        out.append(f"[{s.name}] {s.summary} ({s.ms} ms{tok})")
        if s.name.startswith("5") and t.pre_guard:
            p = t.pre_guard
            out.append(f"    before guard: {p.action} | {p.category} | {p.priority} | {p.team} | approval={p.approval_required}")
            out.append(f"    reply before guard: {compact(p.user_reply, 400)}")
        elif s.output not in (None, [], {}):
            out.append(f"    {compact(s.output)}")
    d = t.decision
    out += ["", f"FINAL: {d.action} | {d.category} | {d.priority} | {d.team}" + (f" | {d.incident_id}" if d.incident_id else ""),
            f"approval: {d.approval_required} ({d.approver})  status: {d.ticket_status}",
            f"fields: {[(f.name, f.value) for f in d.ticket_fields]}  missing: {d.missing_fields}",
            f"reply: {d.user_reply}", f"cited: {d.cited_kb}  agent note: {d.agent_note}",
            f"total {t.total_ms} ms, tokens {t.tokens}"]
    return "\n".join(out)


def batch_table(traces: list[Trace]) -> str:
    rows = [f"{'request':10} {'channel':16} {'action':18} {'category':14} {'prio':5} {'team':32} {'incident':9} fixes"]
    for t in traces:
        d = t.decision
        rows.append(f"{t.request_id:10} {t.channel:16} {d.action:18} {d.category:14} {d.priority:5} {d.team:32} "
                    f"{d.incident_id or '-':9} {sorted({f['rule'] for f in t.guard_fixes})}")
    return "\n".join(rows)
