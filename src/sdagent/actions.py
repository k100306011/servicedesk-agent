"""Step 7: act through simulated ITSM tools that write to SQLite.
create_ticket, link_to_incident, request_info and notify_security. The agent never makes the risky change itself:
tickets that need approval wait in the review console until a person approves them. Every call goes to audit_log.
In production these become ServiceNow or Dynamics 365 APIs under an agent identity with least privilege.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .data import RUNTIME, routing
from .models import Decision, Request

DB_PATH = RUNTIME / "servicedesk.db"
LOCK = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, request_id TEXT, kind TEXT, category TEXT, priority TEXT,
  team TEXT, status TEXT, incident_id TEXT, approval_required INTEGER, approver TEXT, fields TEXT, missing TEXT,
  summary TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS links (request_id TEXT, incident_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS messages (request_id TEXT, direction TEXT, text TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT, approver TEXT, status TEXT,
  decided_by TEXT, decided_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS security_notices (request_id TEXT, reason TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, tool TEXT,
  request_id TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS traces (request_id TEXT, config TEXT, profile TEXT, created_at TEXT, json TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def reset(path: Path | str = DB_PATH) -> None:
    Path(path).unlink(missing_ok=True)
    connect(path).close()


def audit(db, actor: str, tool: str, request_id: str, detail: dict) -> None:
    db.execute("INSERT INTO audit_log (ts, actor, tool, request_id, detail) VALUES (?,?,?,?,?)",
               (now(), actor, tool, request_id, json.dumps(detail, ensure_ascii=False)))


def create_ticket(db, request_id: str, d: Decision, kind: str, status: str, summary: str) -> str:
    n = db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] + 1
    tid = f"TCK-{n:04d}"
    fields = {f.name: f.value for f in d.ticket_fields}
    db.execute("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, request_id, kind, d.category, d.priority, d.team, status, d.incident_id, int(d.approval_required),
                d.approver, json.dumps(fields, ensure_ascii=False), json.dumps(d.missing_fields), summary, now()))
    if status == "pending_approval":
        db.execute("INSERT INTO approvals (ticket_id, approver, status) VALUES (?,?,?)", (tid, d.approver, "pending"))
    audit(db, "agent", "create_ticket", request_id, {"ticket": tid, "kind": kind, "status": status, "team": d.team})
    return tid


def update_ticket(db, ticket_id: str, request_id: str, d: Decision, status: str) -> None:
    """A later turn of the same conversation fills in fields: update the open ticket, do not open a second one."""
    fields = {f.name: f.value for f in d.ticket_fields}
    db.execute("UPDATE tickets SET category=?, priority=?, team=?, status=?, approval_required=?, approver=?, fields=?, "
               "missing=? WHERE id=?", (d.category, d.priority, d.team, status, int(d.approval_required), d.approver,
                                        json.dumps(fields, ensure_ascii=False), json.dumps(d.missing_fields), ticket_id))
    if status == "pending_approval" and not db.execute(
            "SELECT 1 FROM approvals WHERE ticket_id=? AND status='pending'", (ticket_id,)).fetchone():
        db.execute("INSERT INTO approvals (ticket_id, approver, status) VALUES (?,?,?)", (ticket_id, d.approver, "pending"))
    audit(db, "agent", "update_ticket", request_id, {"ticket": ticket_id, "status": status})


def link_to_incident(db, request_id: str, incident_id: str) -> None:
    db.execute("INSERT INTO links VALUES (?,?,?)", (request_id, incident_id, now()))
    audit(db, "agent", "link_to_incident", request_id, {"incident": incident_id})


def request_info(db, request_id: str, fields: list[str]) -> None:
    audit(db, "agent", "request_info", request_id, {"fields": fields})


def notify_security(db, request_id: str, reason: str) -> None:
    db.execute("INSERT INTO security_notices VALUES (?,?,?)", (request_id, reason, now()))
    audit(db, "agent", "notify_security", request_id, {"reason": reason})


def act(db, req: Request, d: Decision, incident_kind: bool, notify: str = "") -> list[dict]:
    """Turn the final decision into tool calls. Email and phone cannot ask back in real time,
    so ask_clarifying there opens a ticket that waits for the user (assumption A4)."""
    done, async_channel = [], req.channel in routing()["async_channels"]
    with LOCK:
        if d.action in ("create_ticket", "escalate_security", "human_triage") or (d.action == "ask_clarifying" and async_channel):
            kind = {"escalate_security": "security", "human_triage": "triage"}.get(d.action, "incident" if incident_kind else "request")
            status = d.ticket_status
            if d.action == "ask_clarifying" or (d.missing_fields and status == "new"):
                status = "pending_user"
            if d.action == "create_ticket" and d.approval_required:
                status = "pending_approval"
            open_ticket = db.execute("SELECT id FROM tickets WHERE request_id=? AND kind=? AND status IN "
                                     "('new','pending_user','pending_approval') ORDER BY id DESC", (req.request_id, kind)).fetchone()
            if open_ticket:
                update_ticket(db, open_ticket["id"], req.request_id, d, status)
                done.append({"tool": "update_ticket", "ticket": open_ticket["id"], "kind": kind, "status": status})
            else:
                tid = create_ticket(db, req.request_id, d, kind, status, d.agent_note[:300])
                done.append({"tool": "create_ticket", "ticket": tid, "kind": kind, "status": status})
        if d.action == "link_incident" and d.incident_id:
            link_to_incident(db, req.request_id, d.incident_id)
            done.append({"tool": "link_to_incident", "incident": d.incident_id})
        if d.action == "ask_clarifying" or d.missing_fields:
            request_info(db, req.request_id, d.missing_fields)
            done.append({"tool": "request_info", "fields": d.missing_fields})
        if d.action == "escalate_security" or notify:
            notify_security(db, req.request_id, notify or "security escalation")
            done.append({"tool": "notify_security", "reason": notify or "security escalation"})
        db.execute("INSERT INTO messages VALUES (?,?,?,?)", (req.request_id, "agent", d.user_reply, now()))
        db.commit()
    return done


def decide_approval(db, ticket_id: str, approved: bool, by: str, note: str = "", edits: dict | None = None) -> None:
    """Human step in the review console: Approve, Edit & approve, or Reject."""
    with LOCK:
        if edits:
            row = db.execute("SELECT fields FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            fields = {**json.loads(row["fields"]), **edits}
            db.execute("UPDATE tickets SET fields=? WHERE id=?", (json.dumps(fields, ensure_ascii=False), ticket_id))
        status = "approved" if approved else "rejected"
        db.execute("UPDATE approvals SET status=?, decided_by=?, decided_at=?, note=? WHERE ticket_id=? AND status='pending'",
                   (status, by, now(), note, ticket_id))
        db.execute("UPDATE tickets SET status=? WHERE id=?", ("approved" if approved else "rejected", ticket_id))
        audit(db, f"human:{by}", "approve" if approved else "reject", ticket_id, {"note": note, "edits": edits or {}})
        db.commit()


def save_trace(db, trace_json: str, request_id: str, config: str, profile: str) -> None:
    with LOCK:
        db.execute("INSERT INTO traces VALUES (?,?,?,?,?)", (request_id, config, profile, now(), trace_json))
        db.commit()
