# How I used AI tools

The brief allows AI-assisted development and asks me to say how I used it. I used an AI coding assistant (Claude Code) in the terminal, as a pair programmer that works from my written plan.

## What the assistant did

- First drafts of the Python modules, the tests, the Streamlit app and the docs, step by step from my plan.
- The synthetic holdout (36) and red-team (12) items, from my list of traps, before any rule existed.
- A first draft of the rubric for the 12 incoming requests, written from the KB.
- Checking Azure product names, GA or preview status and prices on Microsoft Learn, with links and dates.
- Running the test and evaluation commands, and a first draft of the error analysis.
- First passes of the human-review scores (`eval/human_scores.csv`) and of the second check of the label corrections, each with its KB reason.

## What I did

- Framed the problem and set the scope: triage and safe handling, two kinds of users, nothing that changes systems without a person.
- Set the success criteria and thresholds before any code, and the trust order for the data (KB, then incidents, then historical labels).
- Reviewed and approved the rubric, the label corrections and every guard rule against the KB.
- Chose the design: a fixed pipeline, a guard after the model, an incident check on every request, BM25 instead of a vector store, and fail-closed structured output.
- Reviewed the results, the guard fixes and the human-review sheet, and decided what to tune (at most two rounds, prompts and config only).
- Ran the prototype myself and changed it by hand (see the exercises in the README: add a rule, change a priority, add a KB article, switch models).

## How the work was verified

- `pytest`: every guard rule G1–G12 has an English and a Chinese test, plus redaction, incident matching, retrieval and fail-closed tests.
- A rubric and test sets frozen before tuning (`eval/FROZEN.md`); three runs per configuration; criteria judged on the worst run.
- A checker with its own patterns, separate from the guard, and a human-review sheet for every case the rules cannot decide (`eval/human_review.md`).
- Comparison groups B0–B3, so each layer has to show its value in numbers.

## Time

The brief recommends no more than eight hours. I spent about four hours in total:

- Planning before the build: scope, success criteria, test design and a step plan.
- Build, evaluation and documents with the assistant: about 2.5 hours on 2026-11-24 (13:57 to 16:30; the build commits run from 14:12 to 15:56).
- After that: review of the human-review scores and the label corrections on 2026-11-25, the hands-on changes and the demo rehearsal.
