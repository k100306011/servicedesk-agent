"""Step 4: retrieve knowledge.
BM25 over Active KB articles only: deprecated articles (KB-011) are never indexed, so they can never be cited.
Three similar resolved tickets come back as precedents, labeled "examples, not policy".
Twelve short articles do not need a vector database. Below the score threshold we return no KB at all.
"""
from __future__ import annotations

import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from .data import historical_tickets, kb_articles, routing

STOP = set("""a an the and or but if of to in on at for from by with without is are was were be been being it its this that
these those i me my we our you your he she they them their can could would should will shall may might must do does did
have has had not no so as than then there here what which who whom how when where why all any some each other only same
just also into about after before again over under up down out very please need needs want get got one""".split())


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP or len(w) < 2:
            continue
        for suffix in ("ing", "es", "ed", "s"):  # tiny stemmer: freezes/freezing -> freez
            if len(w) > 5 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


@lru_cache
def kb_index() -> tuple[BM25Okapi, list[dict]]:
    docs = [a for a in kb_articles() if a["status"].lower() == "active"]
    return BM25Okapi([tokens(f"{a['title']} {a['applies_to']} {a['body']}") for a in docs]), docs


@lru_cache
def precedent_index() -> tuple[BM25Okapi, list[dict]]:
    docs = [t for t in historical_tickets() if t["status"] == "resolved" and t["resolution_summary"]]
    return BM25Okapi([tokens(f"{t['subject']} {t['description']}") for t in docs]), docs


def search_kb(query: str, k: int | None = None, min_score: float | None = None) -> list[dict]:
    cfg = routing()["retrieval"]
    k, min_score = k or cfg["kb_top_k"], cfg["kb_min_score"] if min_score is None else min_score
    q = tokens(query)
    if not q:
        return []
    bm25, docs = kb_index()
    scored = sorted(zip(bm25.get_scores(q), docs), key=lambda x: -x[0])
    return [{"id": d["id"], "title": d["title"], "score": round(float(s), 2), "text": d["text"]}
            for s, d in scored[:k] if s >= min_score]


def search_precedents(query: str, exclude: str = "", k: int | None = None) -> list[dict]:
    """Leave-one-out: the ticket being evaluated (exclude) is never its own precedent."""
    k = k or routing()["retrieval"]["precedents_k"]
    q = tokens(query)
    if not q:
        return []
    bm25, docs = precedent_index()
    scored = sorted(zip(bm25.get_scores(q), docs), key=lambda x: -x[0])
    out = [{"id": t["ticket_id"], "score": round(float(s), 2), "category": t["category"], "team": t["assigned_team"],
            "priority": t["priority"], "summary": f"{t['subject']}: {t['description']}",
            "resolution": t["resolution_summary"]} for s, t in scored if t["ticket_id"] != exclude and s > 0]
    return out[:k]


def retrieve(query: str, default_kb: str = "", exclude: str = "") -> dict:
    """KB hits plus precedents. default_kb is the article of the guessed category. It is added when BM25 missed it,
    for example a Chinese request in offline mode, or a phishing story that never uses the word "phishing"."""
    hits = search_kb(query)
    if default_kb and default_kb not in {h["id"] for h in hits}:
        art = next((a for a in kb_articles() if a["id"] == default_kb and a["status"].lower() == "active"), None)
        if art:
            hits.append({"id": art["id"], "title": art["title"], "score": 0.0, "text": art["text"], "via": "category default"})
    return {"kb": hits, "precedents": search_precedents(query, exclude=exclude)}
