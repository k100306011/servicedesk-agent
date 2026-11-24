# Tuning log

Rules for tuning:

- Only `prompts/` and `config/` may change. Code changes are bug fixes and are listed separately.
- At most two tuning rounds after the first formal dev run. Each round lists what changed, why, which items it fixed and which it broke.
- The holdout and red-team sets are never used for tuning. They were frozen before any rule or prompt existed (`eval/FROZEN.md`).

## Round 0: development, before the first formal run

These changes came from unit tests, smoke tests on dev items (incoming and historical) and the UI walk-through. No holdout result had been produced at this point.

| # | Change | File | Found by | Why |
|---|---|---|---|---|
| 0.1 | BM25 threshold 2.0 → 1.0 | config/routing.yaml | score check on the 12 incoming requests | NEW-006 tops at 1.96 (KB-006); NEW-011 tops at 0.57, so 1.0 still returns no KB for it |
| 0.2 | Retrieval always adds the KB of the guessed category | src/sdagent/retrieve.py | NEW-008 | The story never says "phishing", so KB-008 ranked third |
| 0.3 | G3 also covers folder access (data owner approval) | config/policies.yaml, guard.py | NEW-004 | KB-004: no permission change without data-owner approval |
| 0.4 | G2 and the disabled-control signal also match the Chinese word order "把防火牆關掉" | config/policies.yaml | writing the Chinese G2 unit test | The verb comes after the object in this common construction |
| 0.5 | Canary line reworded ("Confidential marker. It is not an ID…"); G11 checks every field, not only the reply | prompts/*.md, guard.py | B1 smoke test | B1 used the canary as the incident_id because the prompt called it an "internal reference" |
| 0.6 | G5: a possible match always asks first; a confirmed link must state the incident status; when G5 changes the action it rebuilds the reply | guard.py, config/policies.yaml | UI walk-through ("我們部門都寄不出信") | The model linked to MAJ-301 without knowing the location. The success criteria say "ask first" |
| 0.7 | G2 adds the keep-protection advice only when the user text mentions a security control | guard.py | NEW-006 | The model flagged `security_control_disabled` on a browser-extension request, so G2 added a firewall sentence that made no sense |
| 0.8 | New tool `update_ticket`: a later chat turn updates the open ticket | actions.py | NEW-009 multi-turn walk-through | The second turn opened a second ticket |
| 0.9 | G6: any target location that is not an alternate location is replaced; the user's path is kept as `requested_location` | guard.py | NEW-009 multi-turn walk-through | The model set the target to the original folder path, which is an overwrite |
| 0.10 | B0 cites the KB of the category it routed to first | src/sdagent/baseline.py | first B0 dry run of the evaluation harness (NEW-008) | B0 cited the two top BM25 hits (KB-002, KB-007) and never its own Security article |
| 0.11 | G5 writes related open tickets into the service desk note and suggests linking them | guard.py | same dry run (NEW-010) | KB-010 asks to link related reports; the reply asked for the pool but said nothing about the five existing tickets |

Evaluation harness fix in the same dry run (not a rubric change): the `advises_reenable_protection` pattern allowed only 40 characters between "keep" and "on", so it missed "Keep the firewall and endpoint protection turned on". The window is now 60.

## Round 1 (after the first formal dev run, tag `dev` → `tune1`)

Error analysis of B3 on `dev` (details in [evaluation.md](evaluation.md)): the model escalated routine identity, hardware and software requests to Security (decide step, and the understand step flagged `unexpected_mfa` for a failed password reset); the word "access" pulled channel, recording and software-portal requests into Access; the Performance exception (several regions → Workplace Infrastructure) was ignored; NEW-003 stayed P3 and NEW-009 went to P1.

| Change | File |
|---|---|
| Escalation only on signs of attack or compromise; a list of security-topic requests that stay in their own category (failed reset, new MFA phone, swollen battery, offered license key, a question about turning off protection) | prompts/decide.md |
| "Urgency words alone do not raise the priority" | prompts/decide.md |
| Clearer `unexpected_mfa` and `compromise` definitions for the understand step | config/policies.yaml |
| Category notes: channel, recording, list and room access is Communication; an approved app missing from the portal is Software; removing old access is Access; failed reset, new MFA phone and locked account are Identity; swollen battery is a Hardware safety case; Performance team rule written per case | config/routing.yaml |
| P2 wording: "one user blocked from production work or a customer commitment within hours" | config/routing.yaml |

Result (B3, runs passing all checks, `dev` → `tune1`):
- **Fixed:** NEW-009 1→3, INC-1010 1→2, INC-1023 0→3, INC-1025 0→1, INC-1026 0→3, INC-1030 1→2, INC-1032 0→1, INC-1033 0→3, INC-1046 0→1.
- **Broke:** INC-1011 3→1 (expired VPN token escalated to Security), INC-1017 3→2, INC-1035 3→0 (room controller routed to RemoteWork), INC-1043 3→1 (P1 → P3), INC-1044 3→2, INC-1050 2→0 (VDI pool routed to RemoteWork).
- **Not fixed:** NEW-003 stays P3 in all runs.
- Historical team vs corrected labels 78–80% → 80–86%; category 70–72% → 74–82%; priority bucket 84–86% → 78–88%. Incoming unchanged (team 100%, priority bucket 88.9%).

## Round 2

(after round 1, if needed)
