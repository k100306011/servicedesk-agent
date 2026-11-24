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

## Round 1

(after the first formal dev run)

## Round 2

(after round 1, if needed)
