"""Pipeline: run the 7 steps in a fixed order and record a trace for every request.
The order lives in code; the model only fills two steps (understand, decide). Configurations:
B0 = no model (rules), B1 = one model call only, B2 = steps 2-5 without sanitize and guard, B3 = all 7 steps.
A model failure never stops the flow: it fails closed to human_triage.
"""
from __future__ import annotations

import secrets
import time

from . import actions
from .baseline import decide_offline, language, reply, understand_offline
from .correlate import correlate
from .data import DATA, historical_tickets, incoming_requests, read_jsonl, routing
from .decide import decide, decide_llm_only, normalize
from .guard import Guard
from .llm import LLM
from .models import Correlation, Decision, Request, Step, Trace
from .retrieve import retrieve
from .sanitize import mask_known, sanitize
from .understand import understand

_LLM: dict[str, LLM] = {}


def get_llm(profile: str) -> LLM:
    if profile not in _LLM:
        _LLM[profile] = LLM(profile)
    return _LLM[profile]


def load_set(name: str) -> list[Request]:
    if name == "incoming":
        return [Request(**r, source="incoming") for r in incoming_requests()]
    if name == "historical":
        return [Request(request_id=t["ticket_id"], received_at=t["created_at"], channel=t["channel"],
                        requester_id=t["requester_id"], message=f"{t['subject']}. {t['description']}", source="historical")
                for t in historical_tickets()]
    if name in ("holdout", "redteam"):
        return [Request(**r, source=name) for r in read_jsonl(DATA / "synthetic" / f"{name}.jsonl")]
    if name == "dev":
        return load_set("incoming") + load_set("historical")
    if name == "final":
        return load_set("holdout") + load_set("redteam")
    raise ValueError(f"unknown set {name}")


def find_request(request_id: str) -> Request:
    for name in ("incoming", "historical", "holdout", "redteam"):
        for r in load_set(name):
            if r.request_id == request_id:
                return r
    raise SystemExit(f"request {request_id} not found")


def free_text_request(text: str, channel: str = "chat", history: list[dict] | None = None) -> Request:
    return Request(request_id=f"CHAT-{secrets.token_hex(3)}", received_at=routing()["demo_clock"], channel=channel,
                   message=text, source="chat", history=history or [])


def fail_closed(lang: str, why: str) -> Decision:
    return Decision(action="human_triage", category="none", priority="none", team="none", incident_id="",
                    approval_required=False, approver="", ticket_status="new", ticket_fields=[], missing_fields=[],
                    user_reply=reply("human_triage", lang), agent_note=f"Failed closed: {why}", cited_kb=[], confidence=0.0)


def record(trace: Trace, name: str, summary: str, output, meta: dict | None = None, t0: float | None = None) -> None:
    meta = meta or {}
    ms = meta.get("ms") or (int((time.perf_counter() - t0) * 1000) if t0 else 0)
    tokens = {k: meta[k] for k in ("prompt_tokens", "completion_tokens", "calls", "mode", "errors") if meta.get(k)}
    trace.steps.append(Step(name=name, summary=summary, output=output, ms=ms, tokens=tokens))


def run_request(req: Request, config: str = "B3", profile: str = "local", db=None, save: bool = True) -> Trace:
    start, db = time.perf_counter(), db or actions.connect()
    canary = "CANARY-" + secrets.token_hex(6)
    trace = Trace(request_id=req.request_id, config=config, profile=profile, channel=req.channel, canary=canary)
    llm = get_llm(profile) if config != "B0" else None
    user_turns = [h["text"] for h in req.history if h["role"] == "user"] + [req.message]

    # 1. sanitize (B0, B3)
    t0 = time.perf_counter()
    use_guard = config in ("B0", "B3")
    s = sanitize("\n".join(user_turns)) if use_guard else {
        "text": "\n".join(user_turns), "redacted": [], "injection": [], "signals": [], "open_tag": "", "close_tag": "",
        "wrapped": "\n".join(user_turns), "_secret_values": []}
    if use_guard:
        history = [{**h, "text": sanitize(h["text"])["text"]} for h in req.history]
        current = sanitize(req.message)
        prompt_text = f"{s['open_tag']}\n{current['text']}\n{s['close_tag']}"
    else:
        history, prompt_text = req.history, req.message
    trace.message = s["text"]
    record(trace, "1 sanitize", "secrets masked, injection flagged, text spotlighted" if use_guard else "skipped (no sanitize in this config)",
           {"redacted": s["redacted"], "injection": s["injection"], "signals": s["signals"]}, t0=t0)
    lang, u, corr, kb_ids = language(s["text"]), None, Correlation(), []

    if config == "B1":
        d, meta = decide_llm_only(llm, prompt_text, req.channel, canary, history)
        record(trace, "5 decide (model only)", "one model call, no KB, no incidents", d.model_dump() if d else None, meta)
        d = d or fail_closed(lang, "model output was not valid JSON")
    else:
        # 2. understand
        t0 = time.perf_counter()
        if config == "B0":
            u, meta = understand_offline(s["text"]), {}
        else:
            u, meta = understand(llm, prompt_text, req.channel, canary, history, s["open_tag"], s["close_tag"])
        record(trace, "2 understand", "keyword tables" if config == "B0" else "model -> Understanding JSON",
               u.model_dump() if u else None, meta, t0)
        if u is None:
            d = fail_closed(lang, "understanding was not valid JSON")
        else:
            lang = u.language
            # 3. correlate: every request, every time
            t0 = time.perf_counter()
            corr = correlate(s["text"], req.received_at, u, exclude=req.request_id)
            record(trace, "3 correlate", f"incident check: {corr.status} {corr.incident_id}".strip(),
                   corr.model_dump(exclude={"incident"}) | {"incident": corr.incident}, t0=t0)
            # 4. retrieve
            t0 = time.perf_counter()
            query = " ".join(u.search_keywords + [u.service] + u.symptoms + ([s["text"]] if lang == "en" else []))
            default_kb = routing()["categories"].get(u.category_guess, {}).get("kb", "")
            got = retrieve(query, default_kb, exclude=req.request_id)
            kb_ids = [h["id"] for h in got["kb"]]
            record(trace, "4 retrieve", f"KB {kb_ids}, precedents {[p['id'] for p in got['precedents']]}",
                   {"kb": [{k: h[k] for k in ("id", "title", "score") if k in h} | {"via": h.get("via", "bm25")} for h in got["kb"]],
                    "precedents": [{k: p[k] for k in ("id", "score", "category", "team", "priority")} for p in got["precedents"]]}, t0=t0)
            # 5. decide
            t0 = time.perf_counter()
            if config == "B0":
                d, meta = decide_offline(s["text"], u, corr, got["kb"]), {}
            else:
                d, meta = decide(llm, prompt_text, req.channel, canary, history, u, corr, got, s["open_tag"], s["close_tag"])
            record(trace, "5 decide", "rules and templates" if config == "B0" else "model -> Decision JSON",
                   d.model_dump() if d else None, meta, t0)
            d = normalize(d, s["text"]) if d else fail_closed(lang, "decision was not valid JSON")

    trace.pre_guard = d.model_copy(deep=True)
    # 6. guard (B0, B3)
    notify = ""
    if use_guard and d.action != "human_triage":
        t0 = time.perf_counter()
        signals = sorted(set(s["signals"]) | set(u.risk_signals if u else []))
        g = Guard(d, s["text"], lang, signals, s["injection"], corr, kb_ids, canary, s["_secret_values"], req.received_at)
        d = normalize(g.run(), s["text"])
        trace.guard_fixes = g.fixes
        notify = "possible prompt injection" if g.notify_security else ""
        record(trace, "6 guard", f"{len(g.fixes)} fixes: {sorted({f['rule'] for f in g.fixes})}", g.fixes, t0=t0)
    else:
        record(trace, "6 guard", "skipped (no guard in this config)", [])
    # 7. act
    t0 = time.perf_counter()
    incident_kind = d.action == "create_ticket" and u is not None and u.impact_scope == "multiple" and corr.status == "none"
    trace.actions = actions.act(db, req, d, incident_kind, notify)
    record(trace, "7 act", ", ".join(a["tool"] for a in trace.actions) or "no tool call", trace.actions, t0=t0)
    trace.decision = d
    trace.total_ms = int((time.perf_counter() - start) * 1000)
    trace.tokens = {k: sum(st.tokens.get(k, 0) for st in trace.steps) for k in ("prompt_tokens", "completion_tokens", "calls")}
    if save:
        actions.save_trace(db, mask_known(trace.model_dump_json(), s["_secret_values"]), req.request_id, config, profile)
    return trace
