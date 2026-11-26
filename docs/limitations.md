# Limitations

What this prototype does not show, and what I would do about it.

## Data and evaluation
- The data is small and synthetic: 12 incoming requests, 50 historical tickets, 36 holdout and 12 red-team items. The numbers show behavior on these cases; they are not a statistically strong benchmark. One item is about 8 percentage points on the incoming set.
- The same person wrote the rules and the tests. I wrote the rubric, the holdout items and the guard rules. Freezing the sets before any rule existed limits the damage, but the holdout checks overfitting to the dev set; it is not an independent benchmark. Shadow mode on real tickets is the real test.
- The text checks are rule-based. The checker uses regular expressions (written separately from the guard). They miss paraphrases and can misread negation. Unclear cases go to `eval/human_review.md`. I scored them, and the 12 incoming replies, from `eval/human_scores.csv` (see the Human review section in `docs/evaluation.md`). One reviewer on 12 replies is a small sample; production adds sampled reviews by the desk in shadow mode.
- The label corrections are my judgment. I checked all 9 rows of `eval/label_audit.csv` a second time against the KB and confirmed them (the reason is in `review_note`). The process owner has not seen them, so historical scores are reported against both label sets.
- The priority mapping is an assumption (A1 in `docs/data_assessment.md`). The KB has no P1 to P4 scale.

## Agent behavior
- Incident matching uses word lists. Service, symptom and location synonyms live in `config/routing.yaml`. Requests that describe a problem in unusual words can miss a match; the model's reading of the request helps but is not guaranteed. The data has no user location, so the agent asks; production reads it from Microsoft Graph.
- New incidents are not matched later. An incident the agent opens is not used to match the next request in the same run. Production would query open incidents in the ITSM tool.
- Chinese support depends on the model. The KB is English. Retrieval for Chinese text uses the model's English keywords; the offline baseline only has keyword lists.
- The regex guard can over-block or under-block. Example from development: G2 once added firewall advice to a browser-extension request (fixed, see `docs/tuning_log.md`). Every guard change needs the full evaluation.
- Prompt injection is reduced, not solved. Flags, random markers, the G10 floor and the canary make attacks visible and keep the handling strict, but a new phrasing can still get past the regex flags.
- Vague values can pass as filled fields. The model sometimes fills a required field with a vague value instead of listing it as missing, for example `time_observed: Current time` (NEW-012), `time_observed: Time of the incident` (NEW-008) or `restore_point: sometime this week` (NEW-009). The completeness check only sees that a value exists. Next step: the guard rejects vague values and asks for them.
- Small inconsistencies appear across chat turns. In the Chinese email demo the second turn linked the right incident (MAJ-301) but labeled the category Network instead of Communication.
- Conversation memory is short. Each chat turn re-runs the pipeline on the whole conversation. There is no long-term user history.

## Azure
- No numbers were measured on Azure. The azure profile is implemented, contract-tested with a fake HTTP server, and shown to give the same decisions as the local profile when both point at the same server. No live Azure deployment was used, so quality, latency and cost on Azure are not measured. Token counts for Azure are estimates (recounted with `o200k_base`), not billed numbers.
- Model-specific parameters are not verified. The client sends `temperature=0`, `max_completion_tokens` and a strict JSON schema. Some reasoning models reject `temperature`; the contract test checks the request shape, not each model's parameter rules.
- The first step of a real rollout is to run the same frozen dev, holdout and red-team sets in the customer's Azure subscription and compare with the numbers here.

## Engineering
- The tools are simulated. SQLite stands in for the ITSM tool; there is no authentication, no real approvals and no notifications.
- There is one local model: an open-weight 14B model on one RTX 4090. Hosted models will likely score higher; the measured quality is a floor. Latency was measured one request at a time, not under load.
- There is no load or cost test in production conditions. The cost model uses measured tokens and list prices; real cost depends on traffic, caching and the model mix.
