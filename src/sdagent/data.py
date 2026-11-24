"""Load the data package and the YAML config.
Every other module reads tickets, requests, incidents, KB articles and rules through this file,
so all paths live in one place. Config is cached; call reload() after editing a YAML file.
"""
from __future__ import annotations

import csv
import json
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

from . import ROOT

DATA = ROOT / "data"
CONFIG = ROOT / "config"
PROMPTS = ROOT / "prompts"
RUNTIME = ROOT / "runtime"


@lru_cache
def routing() -> dict:
    return yaml.safe_load((CONFIG / "routing.yaml").read_text(encoding="utf-8"))


@lru_cache
def policies() -> dict:
    return yaml.safe_load((CONFIG / "policies.yaml").read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: Path) -> list[dict]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


@lru_cache
def historical_tickets() -> list[dict]:
    return read_csv(DATA / "historical_tickets.csv")


@lru_cache
def incoming_requests() -> list[dict]:
    return read_jsonl(DATA / "incoming_requests.jsonl")


@lru_cache
def incidents() -> list[dict]:
    # SDAGENT_INCIDENTS lets you point at a test copy without touching the original file.
    path = os.getenv("SDAGENT_INCIDENTS", str(DATA / "current_incidents.csv"))
    return read_csv(Path(path))


def parse_kb(path: Path) -> dict:
    """Parse one KB markdown file: title line, '- Key: value' metadata, then the body."""
    text = path.read_text(encoding="utf-8")
    title = re.search(r"^# (KB-\d+): (.+)$", text, re.M)
    meta = dict(re.findall(r"^- ([A-Za-z ]+): (.+)$", text, re.M))
    body = re.split(r"\n\n", text, maxsplit=2)[-1].strip()
    return {
        "id": title.group(1), "title": title.group(2).strip(), "path": path.name,
        "owner": meta.get("Owner", ""), "last_reviewed": meta.get("Last reviewed", ""),
        "status": meta.get("Status", ""), "superseded_by": meta.get("Superseded by", ""),
        "applies_to": meta.get("Applies to", ""), "body": body, "text": text,
    }


@lru_cache
def kb_articles() -> list[dict]:
    return [parse_kb(p) for p in sorted((DATA / "knowledge-base").glob("KB-*.md"))]


def kb_by_id() -> dict[str, dict]:
    return {a["id"]: a for a in kb_articles()}


def active_kb_ids() -> set[str]:
    return {a["id"] for a in kb_articles() if a["status"].lower() == "active"}


def reload() -> None:
    """Clear cached config and data, for example after editing policies.yaml in the app."""
    for fn in (routing, policies, historical_tickets, incoming_requests, incidents, kb_articles):
        fn.cache_clear()
