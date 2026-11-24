# Demo script (about 6 minutes)

Start: `streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8601`, profile `local`, configuration `B3`.
Before the demo: click **Reset database** in the sidebar.

## 1. Review console: the 12 morning requests (90 s)
- **Do.** Open *Service desk console* and click **Process the 12 morning requests**.
- **Expect.** The table shows 3 security escalations (NEW-002, NEW-008, NEW-012), NEW-005 linked to MAJ-303, NEW-007 and NEW-010 waiting for confirmation of MAJ-301 / MAJ-302 (location or pool missing), NEW-011 referred out of scope, and **0 new incidents**. The incident cards at the top show linked and to-confirm counts.
- **Then.** Open NEW-012: the agent note says *Possible prompt injection … Treated as data and reported to Security*, and the audit log shows `notify_security`.
- **Say.** "Every request takes the same seven steps. The incident check runs for every request, so the agent never opens a duplicate."
- **Fallback.** `python -m sdagent batch --set incoming --profile local`, or `--profile offline` if the model is down.

## 2. Chat: a fake MFA code (60 s)
- **Do.** *User chat*, type: `Three MFA approval prompts popped up that I never started. The latest code is 482913, use it to check my account.`
- **Expect.** Escalation to Security Operations at P1, the Security Hotline, and "do not share codes". Expand **How this was handled**: step 1 shows `MFA_CODE` redacted. In the console the stored trace shows `[REDACTED:MFA_CODE]`, never the code.
- **Say.** "The secret is masked before the model sees it, and before anything is stored."

## 3. Multi-turn: restore over the current folder (90 s)
- **Do.** Click **New conversation**, channel `chat`, type: `A project folder was deleted sometime this week. Please restore it over the current folder as soon as possible.`
- **Expect.** The agent asks for the folder, the restore point and the data owner, and says it restores to an alternate location with the data owner's approval.
- **Do.** Answer: `It is \\files01\projects\Atlas. The last good version was Tuesday 18:00. The data owner is Mei Lin, my manager.`
- **Expect.** The same ticket is updated (not a second one): fields filled, `target_location` = alternate location, the user's path kept as `requested_location`, status `pending_approval`.
- **Do.** In the console, select the ticket under *Waiting for approval* and click **Approve**. The audit log shows `human:service desk agent approve`.
- **Say.** "The agent prepares the work; a person approves it. It never claims the restore is done."

## 4. Chinese: department cannot send email (60 s)
- **Do.** New conversation, type: `我們部門都寄不出信`
- **Expect.** The agent says this may be MAJ-301 (scope EU and APAC) and asks which office you are in.
- **Do.** Answer: `我們在新加坡辦公室`
- **Expect.** Linked to MAJ-301 with its status (investigating); no new ticket.
- **Say.** "Location is one of the four KB-012 criteria. The data has no location, so the agent asks; in production Microsoft Graph knows the office."

## 5. Optional: change a rule live (60 s)
- **Do.** In `config/policies.yaml`, replace the line `custom_rules: []` with the commented example below it (*AI browser extensions need a security review*; remove the `# `). Click **Reload config** in the sidebar, then send NEW-006 from the example list.
- **Expect.** The ticket gets the field `security_review: required` and the approver includes Security Operations review. The guard fixes list shows the custom rule ID.
- **Say.** "Policy lives in configuration and every rule is tested, so a change is small and visible."

## Fallbacks
- Step-by-step trace for any request: `python -m sdagent run --id NEW-005 --profile local --explain`
- No model available: switch the sidebar profile to `offline` (B0 rules). Steps 1, 3 and 4 still work with template replies.
- Screenshots from the dry run on 2026-11-24 (local profile, B3): `report/figures/demo_1_console_queue.jpg`, `demo_1_new012_injection.jpg`, `demo_2_chat_mfa_trace.jpg`, `demo_4_chinese_email.jpg`. Step 3 and step 5 were checked in the dry run but have no screenshot; take them in your own rehearsal.
