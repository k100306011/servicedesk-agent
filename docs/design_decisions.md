# Design decisions

Each decision lists the context, the options I considered, the choice, and what it costs.

## D-01 Scope: triage and safe handling, not only Q&A and not full automation
- **Context.** The brief names fragmented knowledge, uneven ticket quality and repetitive manual work, for both end users and support staff. Almost every incoming request hides a policy trap (shared MFA code, disabled firewall, overwrite restore, injected text).
- **Options.** A: a knowledge Q&A bot. B: triage and handling with human approval. C: full automation that grants access and closes tickets.
- **Choice.** B. The agent triages every request and then answers with a cited KB article, creates a complete ticket, links to an active incident, escalates to Security, refers out-of-scope topics, or asks for missing facts.
- **Cost.** It does not resolve anything by itself, so the saving is in triage and ticket quality, not in closed tickets. A Q&A bot alone would not touch ticket quality or duplicates; full automation is unsafe with this data.

## D-02 A fixed pipeline; the model does two steps
- **Context.** The interview asks me to explain and change everything. Safety steps must never be skipped.
- **Options.** A: one agent that picks its own tools in a loop. B: several cooperating agents. C: a fixed 7-step pipeline where the model only understands and decides.
- **Choice.** C. The order lives in code. The model fills in step 2 (understand) and step 5 (decide).
- **Cost.** Less flexible for unusual requests, and two model calls per request. In return every request takes the same path, the trace is easy to read, and each step can be tested on its own.

## D-03 A rule-based guard after the model
- **Context.** In the first smoke test the model escalated NEW-002 correctly but wrote "we will ensure your account is secure", which KB-008 forbids.
- **Options.** A: rely on prompt instructions. B: add a deterministic guard after the model (G1–G12 in `config/policies.yaml`).
- **Choice.** B, with every rule tied to a KB article and tested in English and Chinese. The decision before the guard stays in the trace.
- **Cost.** Regex rules can over-block (example: G2 once added a firewall sentence to a browser-extension request) and they need maintenance. The difference between "before" and "after" is useful: it counts the mistakes the model makes by itself.

## D-04 Check active incidents for every request
- **Context.** KB-012 says shared-service problems are checked against active incidents first. Duplicate incidents waste time for the whole desk.
- **Options.** A: give the model an "incident search" tool and let it decide. B: run the check on every request with KB-012's four criteria (service, symptom, location, time window).
- **Choice.** B. The result is confirmed, possible (a criterion is missing, so ask first) or none.
- **Cost.** Synonym and location lists need upkeep. The data has no user location, so the agent must ask; in production Microsoft Graph supplies the office.

## D-05 The KB is the policy source; historical labels are examples
- **Context.** 8 tickets go to an unusual team and 4 labels contradict the current KB (for example INC-1016: a denied folder labeled Network).
- **Options.** A: treat labels as ground truth. B: ignore history. C: use history as examples and precedents, and audit the labels against the KB.
- **Choice.** C. `eval/label_audit.csv` lists 9 corrections with their KB reason, all pending review. Historical scores are reported against both the original and the corrected labels.
- **Cost.** The corrections are my judgment until the process owner confirms them, so both numbers are shown.

## D-06 Structured output with validation; fail closed
- **Context.** Free text cannot be routed or tested reliably.
- **Options.** A: parse free text. B: JSON schema output, validated with pydantic.
- **Choice.** B. First `json_schema` (the enum lists are enforced), then JSON mode with validation and one retry with the error message. If that fails, the action becomes `human_triage`.
- **Cost.** Up to three calls in the worst case, and a schema that both vLLM and Azure accept (strict mode, no free-form objects).

## D-07 BM25 plus English keywords from the model, not a vector database
- **Context.** Twelve short articles. Some requests are in Chinese while the KB is in English.
- **Options.** A: embeddings and a vector store. B: BM25 over Active articles, queried with English keywords that the understand step produces.
- **Choice.** B, with a score threshold (no KB → refer, do not invent) and the KB of the guessed category added when BM25 misses it.
- **Cost.** Keyword search misses paraphrases that share no words. In production the knowledge spreads across SharePoint and the ITSM tool, so it moves to Foundry IQ (Azure AI Search) with hybrid search, the semantic ranker, an Active-only filter and permission trimming.

## D-08 A local open-weight model for the prototype, Azure OpenAI by configuration
- **Context.** No cloud keys are needed to run or review the prototype, and the code must move to Azure without a rewrite.
- **Options.** A: build on one cloud API only. B: one OpenAI-compatible client with profiles `offline`, `local` and `azure`.
- **Choice.** B. The prototype runs an open-weight 14B model served by vLLM on a single RTX 4090 workstation; the Azure profile uses the Azure OpenAI v1 endpoint with the standard OpenAI SDK. `offline` runs B0 with no model at all.
- **Cost.** A 14B model is weaker than current hosted models, so the measured quality is a floor, not a ceiling.

## D-09 High-risk actions always need a person
- **Context.** Access, restores and software approval change real systems.
- **Options.** A: let the agent act through APIs. B: the agent prepares the ticket and a person approves it.
- **Choice.** B. Tickets that need approval wait in the review console (Approve, Edit & approve, Reject). Every tool call and every human decision goes to the audit log. The agent cannot set a ticket to resolved (G8).
- **Cost.** Some requests wait longer. In production, pre-approved standard roles can go through Microsoft Entra ID Governance access packages.

## D-10 No agent framework in the prototype; Microsoft Agent Framework in production
- **Context.** I must explain and modify every line, live.
- **Options.** A: LangChain, LlamaIndex or similar. B: plain Python with eight small libraries.
- **Choice.** B for the prototype (about 1,720 lines in `src/`, no file over 250 lines). For production the same steps become executors in a Microsoft Agent Framework workflow, with its human-in-the-loop requests and checkpointing, hosted in Foundry Agent Service.
- **Cost.** I wrote small things a framework would give me (retries, schemas, the trace).

## D-11 Score priority by bucket
- **Context.** The KB says "high" and "medium"; tickets use P1–P4; there is no mapping.
- **Options.** A: score the exact P value. B: score high (P1/P2) versus normal (P3/P4), and report the exact value separately.
- **Choice.** B, with the mapping written down as assumption A1 in `docs/data_assessment.md`.
- **Cost.** A P1/P2 swap is not penalized in the main number. The exact accuracy is still in the results.

## D-12 Evaluation: criteria first, dev and holdout apart, three runs, comparison groups
- **Context.** The brief asks how I validate the outcome, not for one correct answer.
- **Options.** A: try examples by hand. B: a frozen rubric and holdout set, repeated runs, and comparison groups.
- **Choice.** B. Success criteria were written before any code. The holdout (36 paraphrases, Chinese versions and trap versions) and the red-team set (12) were frozen before any rule or prompt existed. B1–B3 run three times; criteria use the worst run. B0 (no model), B1 (model only), B2 (model with KB and incidents) and B3 (everything) show what each layer adds. The checker uses its own patterns, separate from the guard, and sends unclear cases to human review.
- **Cost.** I wrote both the rules and the test items, so the holdout is a check against overfitting to the dev set, not an independent benchmark. The real benchmark is shadow mode on live tickets.
