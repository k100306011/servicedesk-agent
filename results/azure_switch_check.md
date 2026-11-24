# Azure profile switch check

`python -m eval.azure_switch` runs B3 twice per item: `--profile local` and `--profile azure`, with the azure settings pointed at the same local OpenAI-compatible server. **No live Azure deployment was used**; this only shows that switching is a configuration change.

Decision fields: action, category, priority, team, incident_id, approval_required, approver, ticket_status, cited_kb. Reply text and the model's list of missing fields are compared separately, with a control: the local profile run twice. The canary and the spotlighting markers are random on every request, so the prompt differs slightly on every run and the wording can change even inside one profile.

| Item | Decision same: local vs azure | Decision same: local vs local | Text same: local vs azure | Text same: local vs local | Decision (local) | Decision (azure) |
|---|---|---|---|---|---|---|
| NEW-005 | yes | yes | yes | yes | link_incident / Hardware / P2 / Workplace Technology / MAJ-303 | link_incident / Hardware / P2 / Workplace Technology / MAJ-303 |
| NEW-009 | no | no | no | no | create_ticket / DataProtection / P3 / Data Protection / - | create_ticket / DataProtection / P1 / Data Protection / - |
| NEW-012 | yes | yes | no | no | escalate_security / Security / P1 / Security Operations / - | escalate_security / Security / P1 / Security Operations / - |
