"""Data shapes shared by every step.
Each step has one clear contract: what goes in and what comes out.
B0, B1, B2 and B3 all return the same Decision, so one scorer can grade them all.
Understanding and Decision are also the JSON schemas the model must follow.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ACTIONS = ["self_service", "ask_clarifying", "link_incident", "create_ticket",
           "escalate_security", "out_of_scope", "human_triage"]
TICKET_STATUS = ["new", "pending_user", "pending_approval", "resolved", "closed"]


class Request(BaseModel):
    request_id: str
    received_at: str
    channel: str
    requester_id: str = ""
    message: str
    source: str = "incoming"
    history: list[dict] = []  # earlier chat turns: {"role": "user" | "agent", "text": "..."}


class Understanding(BaseModel):
    intent: str
    service: str
    category_guess: str
    symptoms: list[str]
    impact_scope: Literal["single", "multiple", "unknown"]
    requested_action: str
    systems: list[str]
    folders: list[str]
    devices: list[str]
    locations: list[str]
    vdi_pools: list[str]
    risk_signals: list[str]
    missing_info: list[str]
    search_keywords: list[str]
    language: Literal["en", "zh"]


class Correlation(BaseModel):
    status: Literal["confirmed", "possible", "none"] = "none"
    incident_id: str = ""
    incident: dict = {}
    matched: list[str] = []
    missing: list[str] = []
    related_tickets: list[str] = []


class TicketField(BaseModel):
    name: str
    value: str


class Decision(BaseModel):
    action: str
    category: str
    priority: str
    team: str
    incident_id: str
    approval_required: bool
    approver: str
    ticket_status: str
    ticket_fields: list[TicketField]
    missing_fields: list[str]
    user_reply: str
    agent_note: str
    cited_kb: list[str]
    confidence: float

    def field(self, name: str) -> str:
        return next((f.value for f in self.ticket_fields if f.name == name), "")

    def set_field(self, name: str, value: str) -> None:
        self.ticket_fields = [f for f in self.ticket_fields if f.name != name] + [TicketField(name=name, value=value)]
        self.missing_fields = [m for m in self.missing_fields if m != name]


class Step(BaseModel):
    name: str
    summary: str = ""
    output: dict | list | str | None = None
    ms: int = 0
    tokens: dict = {}
    rules: list[str] = []


class Trace(BaseModel):
    request_id: str
    config: str
    profile: str
    channel: str = ""
    message: str = ""  # sanitized text only (raw text in B1/B2, which have no sanitize step)
    canary: str = ""
    steps: list[Step] = []
    pre_guard: Decision | None = None
    decision: Decision | None = None
    guard_fixes: list[dict] = []
    actions: list[dict] = []
    total_ms: int = 0
    tokens: dict = {}

    def step(self, name: str) -> Step | None:
        return next((s for s in self.steps if s.name == name), None)
