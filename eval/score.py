"""Metrics for one run of one configuration on one set, computed only from the raw results lines."""
from __future__ import annotations

from collections import Counter
from statistics import median

INCIDENT_CHECKS = {"location": "links_or_asks_location", "pool_or_region": "links_or_asks_pool"}


def rate(values: list[bool]) -> float | None:
    return round(100 * sum(values) / len(values), 1) if values else None


def p95(values: list[int]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))] / 1000, 2)


def incident_ok(r: dict, g: dict) -> bool | None:
    if g.get("incident", "none") == "none":
        return None
    need = g.get("incident_needs", "none")
    name = INCIDENT_CHECKS.get(need, "links_expected_incident")
    q = r["checks"]["quality"]
    if name in q:
        return q[name]
    d = r["decision"]  # rubric did not list the check: compute it from the decision
    return d["action"] == "link_incident" and d["incident_id"] == g["incident"]


def metrics(items: list[dict], gold: dict) -> dict:
    q = lambda name: [r["checks"]["quality"][name] for r in items if name in r["checks"]["quality"]]
    crit = Counter(k for r in items for k, v in r["checks"]["critical"].items() if v)
    fixes = Counter(f["rule"] for r in items for f in r["guard_fixes"])
    lat = [r["latency_ms"] for r in items]
    m = {"items": len(items), "critical_violations": sum(crit.values()),
         "duplicate_incidents": crit.get("creates_new_incident", 0),
         "human_review": sum(len(r["checks"]["human"]) for r in items),
         "ask_rate": rate([r["decision"]["action"] == "ask_clarifying" for r in items]),
         "human_triage_rate": rate([r["decision"]["action"] == "human_triage" for r in items]),
         "latency_p50_s": round(median(lat) / 1000, 2) if lat else None, "latency_p95_s": p95(lat),
         "tokens_in_avg": round(sum(r["tokens"].get("prompt_tokens", 0) for r in items) / max(1, len(items))),
         "tokens_out_avg": round(sum(r["tokens"].get("completion_tokens", 0) for r in items) / max(1, len(items))),
         "guard_fixes": sum(fixes.values()), "items_fixed_by_guard": sum(1 for r in items if r["guard_fixes"])}
    m |= {f"critical:{k}": v for k, v in sorted(crit.items())}
    m |= {f"fixes:{k}": v for k, v in sorted(fixes.items())}
    if items and items[0]["set"] == "historical":
        for which in ("original", "corrected"):
            for k in ("category", "team", "priority"):
                m[f"{which}_{k}_{'bucket_' if k == 'priority' else ''}acc"] = rate([r["labels"][f"{which}_{k}_ok"] for r in items])
        return m
    inc = [incident_ok(r, gold.get(r["item"], {})) for r in items]
    quality = [v for r in items for k, v in r["checks"]["quality"].items()]
    m |= {"action_acc": rate(q("action_ok")), "category_acc": rate(q("category_ok")), "team_acc": rate(q("team_ok")),
          "priority_exact_acc": rate(q("priority_ok")), "priority_bucket_acc": rate(q("priority_bucket_ok")),
          "incident_acc": rate([v for v in inc if v is not None]), "kb_citation_rate": rate(q("kb_any")),
          "required_fields_rate": rate(q("required_fields_complete")), "quality_pass_rate": rate(quality),
          "scored_items": len(q("team_ok"))}
    return m
