# How I used AI tools

The brief allows AI tools and asks how I used them. I used two AI tools:

- An AI chat assistant. I talked through the plan with it, and later it gave me a second opinion on my review. The decisions in the plan are mine: the scope, the success criteria, the test design and the order of trust in the data.
- An AI coding assistant (Claude Code) in the terminal. It built the project from that plan, one step at a time, and I checked each step.

## What the coding assistant did

- First drafts of the Python modules, the tests, the Streamlit app and the docs.
- The synthetic holdout (36) and red-team (12) items, from my list of traps, before any rule existed.
- A first draft of the rubric for the 12 incoming requests, from the KB.
- Azure product names, GA or preview status and prices from Microsoft Learn, with links and dates.
- Running the tests and the evaluation, and a first draft of the error analysis.
- First-pass scores for the human review (`eval/human_scores.csv`) and a first check of the label corrections, each with a KB reason.

## What I did

- Set the scope: triage and safe handling for two kinds of users, and nothing changes a system without a person.
- Set the success criteria and the thresholds before any code. I also set the order of trust in the data: the KB first, then the incidents, then the historical labels.
- Chose the design: a fixed pipeline, a guard after the model, an incident check on every request, BM25 instead of a vector store, and structured output that fails closed.
- Decided what to tune and when to stop: two rounds at most, prompts and config only.
- Read the 12 replies against the KB and set the final scores. I changed one score: NEW-008 went from 5 to 4, because the reply does not ask when it happened and the ticket stores a placeholder time, like NEW-012. I also rewrote six notes.
- Checked the 9 label corrections against the ticket text and the KB, and kept all 9.

## How the work was verified

- `pytest`: every guard rule, G1 to G12, has an English and a Chinese test. Other tests cover redaction, incident matching, retrieval and fail-closed output.
- The rubric and the test sets were frozen before tuning (`eval/FROZEN.md`). Each configuration ran three times, and each criterion is judged on the worst run.
- A checker with its own patterns, separate from the guard, and a human-review sheet for every case the rules cannot decide (`eval/human_review.md`).
- Comparison groups B0 to B3, so each layer has to show its value in numbers.

## Time

The brief recommends no more than eight hours. I spent about four hours in total:

- Planning before the build: the scope, the success criteria, the test design and a step plan.
- Build, evaluation and documents with the coding assistant: about 2.5 hours on 2026-11-24, from 13:57 to 16:30. The build commits run from 14:12 to 15:56.
- Review on 2026-11-25: the 12 replies, the label corrections and the documents.
- Tidying the text and adding screenshots on 2026-11-26, before the interview: plainer wording in the docs and the generated reports, the demo screenshots for steps 3 and 5, and my slide notes moved out of the repo. It took a little over ten minutes; the commits run from 11:03 to 11:05.
