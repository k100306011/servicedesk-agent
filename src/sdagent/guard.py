"""Step 6: guard. The rules in config/policies.yaml are checked after the decision step.
A violation is fixed (action, team, priority, approval, fields) or the reply is rebuilt from safe text.
The decision before the guard stays in the trace: the difference is the list of mistakes the model made by itself.
Safety does not depend on the prompt alone.
"""
from __future__ import annotations

import re

from .baseline import decide_offline, hits, understand_offline, variant
from .correlate import correlate
from .data import active_kb_ids, policies, routing
from .models import Correlation, Decision

SEC_TEAM = "Security Operations"
KB_ID = re.compile(r"\bKB-\d{3}\b")


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?。！？])\s*|\n+", text) if s.strip()]


def negated(sentence: str) -> bool:
    return re.search(policies()["negation"], sentence) is not None


def violates(sentence: str, patterns: list[str], statements_only: bool = False) -> bool:
    if statements_only and sentence.rstrip().endswith(("?", "？")):
        return False
    return any(re.search(p, sentence) for p in patterns) and not negated(sentence)


class Guard:
    def __init__(self, d: Decision, text: str, lang: str, signals: list[str], injection: list[str],
                 corr: Correlation, kb_ids: list[str], canary: str = "", secrets: list[str] | None = None,
                 received_at: str = ""):
        self.d, self.text, self.lang, self.signals, self.injection = d, text, lang, set(signals), injection
        self.received_at = received_at or routing()["demo_clock"]
        self.corr, self.kb_ids, self.canary, self.secrets = corr, kb_ids, canary, secrets or []
        self.rules, self.fixes, self.notify_security = policies()["rules"], [], False

    def fix(self, rule: str, change: str) -> None:
        self.fixes.append({"rule": rule, "change": change})

    def say(self, rule: str, key: str = "text") -> str:
        return self.rules[rule][key][self.lang]

    def drop(self, rule: str, patterns: list[str], statements_only: bool = False) -> bool:
        kept = [s for s in sentences(self.d.user_reply) if not violates(s, patterns, statements_only)]
        if len(kept) == len(sentences(self.d.user_reply)):
            return False
        self.d.user_reply = " ".join(kept)
        self.fix(rule, "removed a sentence from the reply")
        return True

    def add(self, rule: str, sentence: str, change: str = "added required text to the reply") -> None:
        if sentence not in self.d.user_reply:
            self.d.user_reply = f"{self.d.user_reply} {sentence}".strip()
            self.fix(rule, change)

    def set(self, rule: str, **values) -> None:
        for name, value in values.items():
            if getattr(self.d, name) != value:
                self.fix(rule, f"{name}: {getattr(self.d, name)} -> {value}")
                setattr(self.d, name, value)

    # --- rules, in the order they run ---
    def g11_canary(self) -> None:
        """The canary must not appear in any field: reply, note, IDs or ticket fields."""
        if not self.canary or self.canary not in self.d.model_dump_json():
            return
        clean = self.d.model_dump_json().replace(self.canary, "")
        self.d = Decision.model_validate_json(clean)
        self.d.user_reply, self.d.agent_note = self.say("G11"), "Canary found in the output; reply replaced."
        self.fix("G11", "canary removed from the output and reply replaced")

    def g10_injection(self) -> None:
        if not self.injection:
            return
        self.notify_security = True
        self.d.agent_note = (self.d.agent_note + " " + self.rules["G10"]["note"].format(flags=", ".join(self.injection))).strip()
        pats = [r["pattern"] for r in policies()["injection"]]
        clean = " ".join(s for s in sentences(self.text) if not any(re.search(p, s) for p in pats))
        u = understand_offline(clean)
        floor = decide_offline(clean, u, correlate(clean, self.received_at, u), [])
        rank = policies()["action_strictness"]
        if rank.get(self.d.action, 0) < rank.get(floor.action, 0):
            self.set("G10", action=floor.action, category=floor.category, team=floor.team, priority=floor.priority)
        elif floor.priority.startswith("P") and self.d.priority.startswith("P") and self.d.priority > floor.priority:
            self.set("G10", priority=floor.priority)

    def g4_security(self) -> None:
        r = self.rules["G4"]
        self.drop("G4", r["promises_safe"], statements_only=True)
        self.drop("G4", r["delete_evidence"])
        if not self.signals & set(policies()["escalate_on"]):
            return
        self.set("G4", action="escalate_security", team=SEC_TEAM, priority="P1", approval_required=False)
        if self.d.category not in ("Security", "Identity"):
            self.set("G4", category="Security")
        if not re.search(r["hotline"], self.d.user_reply):
            self.add("G4", self.say("G4"), "added Security Hotline instruction")

    def g5_incident(self) -> None:
        """Confirmed match: link, give the status, no new incident. Possible match: ask first (success criteria)."""
        c, r = self.corr, self.rules["G5"]
        if c.related_tickets and "Related open tickets" not in self.d.agent_note:  # KB-010: link reports, no duplicates
            self.d.agent_note = (f"{self.d.agent_note} Related open tickets: {', '.join(c.related_tickets)}. "
                                 f"Link them to {c.incident_id or 'one incident'} instead of opening duplicates.").strip()
        if self.d.action == "escalate_security":
            return
        inc = c.incident
        values = {"incident_id": c.incident_id, "summary": inc.get("summary", ""), "status": inc.get("status", ""),
                  "scope": inc.get("scope", "")}
        if c.status == "confirmed":
            rebuild = self.d.action != "link_incident"
            self.set("G5", action="link_incident", incident_id=c.incident_id, priority=inc["priority"])
            status_words = r["status_words"].get(inc["status"], [inc["status"]])
            if rebuild:
                self.d.user_reply = r["link_text"][self.lang].format(**values)
                self.fix("G5", "reply rebuilt for the incident link")
            elif c.incident_id not in self.d.user_reply or not any(w in self.d.user_reply.lower() for w in status_words):
                self.add("G5", r["link_text"][self.lang].format(**values), "added incident status")
        elif c.status == "possible":
            need = c.missing[0]
            if self.d.action != "ask_clarifying":
                self.set("G5", action="ask_clarifying", incident_id=c.incident_id)
                self.d.user_reply = r["ask_text"][need][self.lang].format(**values)
                self.fix("G5", "reply rebuilt to ask for the missing match criterion")
            elif not re.search(r["asks"][need], self.d.user_reply):
                self.add("G5", r["ask_text"][need][self.lang].format(**values), "added the missing-criterion question")
        elif self.d.action == "create_ticket" and hits(self.text, routing()["signals"]["multi_user"]) \
                and self.d.priority in ("P3", "P4"):
            self.set("G5", priority="P2")

    def g3_access(self) -> None:
        r = self.rules["G3"]
        if self.drop("G3", r["claims_granted"], True) | self.drop("G3", r["grant_before_approval"]):
            self.add("G3", self.say("G3"))
        if self.d.category != "Access" or self.d.action not in ("create_ticket", "ask_clarifying", "self_service"):
            return
        folder = variant("Access", self.text) == "folder_access" and "privileged_access" not in self.signals
        owner = r["folder_approver"] if folder else r["approver"]
        if self.d.action == "self_service":
            self.set("G3", action="create_ticket")
        self.set("G3", approval_required=True)
        if owner not in self.d.approver.lower():
            self.set("G3", approver=owner)
        if folder or "privileged_access" in self.signals:
            if not re.search(r"(?i)approv|核准", self.d.user_reply):
                self.add("G3", self.say("G3", "folder_text" if folder else "text"))

    def g6_restore(self) -> None:
        r = self.rules["G6"]
        if self.drop("G6", r["agrees_to_overwrite"]) | self.drop("G6", r["claims_restored"], True):
            self.add("G6", self.say("G6"))
        if self.d.category != "DataProtection" or self.d.action not in ("create_ticket", "ask_clarifying"):
            return
        target = self.d.field("target_location")
        if not re.search(r"(?i)alternate|替代|另一個位置", target):  # a real path here may be the original folder
            if target:
                self.d.set_field("requested_location", target)
            self.d.set_field("target_location", r["target_location"])
            self.fix("G6", f"target_location: {target or '(empty)'} -> {r['target_location']}")
        self.set("G6", approval_required=True)
        if "data owner" not in self.d.approver.lower():
            self.set("G6", approver=r["approver"])
        if not re.search(r"(?i)alternate|another location|替代|另一個位置", self.d.user_reply):
            self.add("G6", self.say("G6"))

    def g7_software(self) -> None:
        if self.d.category == "Software" and self.drop("G7", self.rules["G7"]["claims"], statements_only=True):
            self.add("G7", self.say("G7"))
        if self.d.category == "Software" and self.d.action == "create_ticket" and variant("Software", self.text) != "activation":
            self.set("G7", approval_required=True)
            if "manager" not in self.d.approver.lower():
                self.set("G7", approver=self.rules["G7"]["approver"])

    def g12_out_of_scope(self) -> None:
        r = self.rules["G12"]
        oos = hits(self.text, routing()["out_of_scope"]) > 0 and not self.kb_ids
        if not (self.d.action == "out_of_scope" or (oos and self.d.action in ("self_service", "ask_clarifying"))):
            return
        self.set("G12", action="out_of_scope", category="none", team="none", priority="none", approval_required=False)
        self.d.cited_kb, self.d.ticket_fields, self.d.missing_fields = [], [], []
        if any(re.search(p, self.d.user_reply) for p in r["policy_content"]) or not re.search(r["referral"], self.d.user_reply):
            self.d.user_reply = self.say("G12")
            self.fix("G12", "reply replaced with the referral template")

    def g1_secrets(self) -> None:
        r = self.rules["G1"]
        self.drop("G1", r["asks_for_secret"])
        leaked = [s for s in sentences(self.d.user_reply) if "[REDACTED" in s or any(v in s for v in self.secrets)]
        if leaked:
            self.d.user_reply = " ".join(s for s in sentences(self.d.user_reply) if s not in leaked)
            self.fix("G1", "removed a sentence that repeated a secret")
        offered = "secret_offered" in self.signals or "[REDACTED:" in self.text
        if offered and not re.search(r["warns"], self.d.user_reply):
            self.add("G1", self.say("G1"), "added do-not-share warning")

    def g2_bypass(self) -> None:
        about_controls = re.search(r"(?i)firewall|anti-?virus|defender|endpoint protection|防火牆|防毒|端點", self.text)
        if self.drop("G2", self.rules["G2"]["patterns"]) or ("security_control_disabled" in self.signals and about_controls):
            if not re.search(r"(?i)re-?enable|turn(ed)? (it |them )?(back )?on|keep\b.{0,40}\b(on|enabled)|重新開啟|保持.{0,10}開啟", self.d.user_reply):
                self.add("G2", self.say("G2"), "added keep-protection-on advice")

    def g8_status(self) -> None:
        if self.d.ticket_status not in self.rules["G8"]["allowed_status"]:
            self.set("G8", ticket_status="pending_user" if self.d.missing_fields else "new")
        if self.drop("G8", self.rules["G8"]["claims"], statements_only=True):
            self.add("G8", self.say("G8"))

    def g9_citations(self) -> None:
        valid = [k for k in self.kb_ids if k in active_kb_ids()]
        bad = [k for k in self.d.cited_kb if k not in valid]
        if bad:
            self.d.cited_kb = [k for k in self.d.cited_kb if k in valid]
            self.fix("G9", f"removed citations {bad}")
        mentioned = [s for s in sentences(self.d.user_reply) if set(KB_ID.findall(s)) - set(valid)
                     and not re.search(r"(?i)deprecated|retired|no longer|停用|淘汰", s)]
        if mentioned:
            self.d.user_reply = " ".join(s for s in sentences(self.d.user_reply) if s not in mentioned)
            self.fix("G9", "removed a sentence that named a KB outside the retrieved active set")
        if not self.d.cited_kb and valid and self.d.action != "out_of_scope":
            self.d.cited_kb = valid[:1]
            self.fix("G9", f"cited the top retrieved active KB {valid[0]}")

    def custom(self) -> None:
        """Your own rules from policies.yaml (custom_rules): add one without changing code."""
        for r in policies().get("custom_rules") or []:
            if not re.search(r["when"], self.text) or (r.get("category") and self.d.category != r["category"]):
                continue
            if r.get("set"):
                self.set(r["id"], **r["set"])
            for name, value in (r.get("add_fields") or {}).items():
                if self.d.field(name) != str(value):
                    self.d.set_field(name, str(value))
                    self.fix(r["id"], f"{name} = {value}")
            if r.get("approver_add") and r["approver_add"] not in self.d.approver:
                self.set(r["id"], approver=", ".join(x for x in (self.d.approver, r["approver_add"]) if x))
            if r.get("reply"):
                self.add(r["id"], r["reply"][self.lang])

    def run(self) -> Decision:
        for rule in (self.g11_canary, self.g10_injection, self.g4_security, self.g5_incident, self.g3_access,
                     self.g6_restore, self.g7_software, self.g12_out_of_scope, self.g1_secrets, self.g2_bypass,
                     self.g8_status, self.custom, self.g9_citations):
            rule()
        return self.d
