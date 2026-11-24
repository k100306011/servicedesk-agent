"""Step 1: sanitize the text before anything else sees it.
Secrets (passwords, MFA codes, recovery codes, license keys, tokens) become markers like [REDACTED:MFA_CODE],
so they never reach the model, SQLite or a trace. Prompt-injection phrases are flagged here, before the model.
The text is then wrapped in random markers (spotlighting): the prompt says text inside them is data, not instructions.
"""
from __future__ import annotations

import re
import secrets

from .data import policies


def redact(text: str) -> tuple[str, list[str], list[str]]:
    """Return (clean text, secret types found, secret values found). Values stay in memory only."""
    types, values = [], []
    for rule in policies()["redaction"]:
        if rule.get("context") and not re.search(rule["context"], text):
            continue
        for m in list(re.finditer(rule["pattern"], text)):
            value = m.group(1)
            if value and value in text:
                text = text.replace(value, f"[REDACTED:{rule['type']}]")
                types.append(rule["type"])
                values.append(value)
    return text, types, values


def find_injection(text: str) -> list[str]:
    return [r["id"] for r in policies()["injection"] if re.search(r["pattern"], text)]


def detect_signals(text: str) -> list[str]:
    """Signals from policies.yaml (security, secrets, privileged access, restore...) found in the text."""
    found = []
    for name, rules in policies()["signals"].items():
        for r in rules:
            if re.search(r["pattern"], text) and (not r.get("context") or re.search(r["context"], text)) \
                    and not (r.get("unless") and re.search(r["unless"], text)):
                found.append(name)
                break
    return found


def spotlight(text: str) -> tuple[str, str, str]:
    """Wrap untrusted text in markers that change on every request, so the text cannot fake the end marker."""
    tag = secrets.token_hex(4)
    open_tag, close_tag = f"<<DATA {tag}>>", f"<<END DATA {tag}>>"
    return open_tag, close_tag, f"{open_tag}\n{text}\n{close_tag}"


def sanitize(text: str) -> dict:
    clean, types, values = redact(text)
    open_tag, close_tag, wrapped = spotlight(clean)
    return {"text": clean, "redacted": types, "injection": find_injection(text), "signals": detect_signals(text),
            "open_tag": open_tag, "close_tag": close_tag, "wrapped": wrapped, "_secret_values": values}


def mask_known(text: str, values: list[str]) -> str:
    """Last line of defense before writing anything: mask secret values seen in this request."""
    for v in sorted(set(values), key=len, reverse=True):
        text = text.replace(v, "[REDACTED]")
    return text
