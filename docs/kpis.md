# How to measure success

Technical numbers from the prototype say whether the agent is safe and correct on a fixed test set.
Business KPIs say whether it helps users and the desk. Production needs both.

| Area | KPI | How production measures it | Prototype metric today |
|---|---|---|---|
| User experience | Time to first useful answer; self-service resolution rate; satisfaction | ITSM timestamps; short survey after the reply | Latency p95 per request; share of `self_service` answers with a cited KB |
| Desk efficiency | Triage time; reassignments; first-time-right routing; ticket completeness | ITSM fields and assignment history | Team accuracy; `required_fields_complete` |
| Major incidents | Duplicate tickets per incident; share of reports linked to the right incident | Incident–ticket links | Duplicate incidents = 0; incident link-or-ask accuracy |
| Risk | Secrets in tickets or logs; unauthorized changes; non-compliant replies | Audit log, DLP, sampled human review | Critical violations = 0; guard fixes by rule |
| Cost | Model cost per request; staff time saved | Usage reports; time studies | Tokens per request ([cost_model.md](cost_model.md)) |

## How to measure

1. Baseline first: run shadow mode for 2 to 4 weeks. The agent proposes and people decide. This gives the baseline for triage time and reassignments, and the agreement rate between agent and desk.
2. Compare by queue in assisted mode: turn on assisted mode for some queues first and compare them with queues that still work the old way. Use the same period, so seasonality and incident load do not distort the result.
3. Weekly regression: run the frozen dev, holdout and red-team sets on every change to prompts, rules or models, and every week. Release only when critical violations stay at 0.
4. Monthly review with the knowledge owners: look at which guard rules fired, which requests had no KB match and which labels were corrected. Each KB gap becomes a new or updated article.

## Targets for the first production quarter (proposal)

These are starting points to agree with the service owner, not measured results:

- Critical violations in sampled human review: 0.
- Duplicate incidents for shared-service outages: down compared with the shadow-mode baseline.
- First-time-right routing: at least the shadow-mode agreement rate, then rising.
- Ticket completeness (KB-required fields present or asked for): close to 100%.
- Time to first useful answer: seconds instead of the queue wait time.
