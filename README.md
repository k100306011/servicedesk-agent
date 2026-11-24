# Service Desk Triage Agent (prototype)

An AI agent that triages incoming IT service desk requests and handles each one safely:
it answers with a cited KB article, creates a complete ticket, links the request to an active incident,
escalates security signals, refers out-of-scope questions, or asks for what is missing.
A service desk agent approves every high-risk action in a review console.

## Quickstart (no keys, about 2 minutes)

The `offline` profile needs no model. It runs B0 (rules only), so you can try every screen.

macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
python -m sdagent batch --set incoming --profile offline
streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8601
```

Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
python -m sdagent batch --set incoming --profile offline
streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8601
```

Then open http://127.0.0.1:8601. Python 3.11 or later. `make setup test batch app` are shortcuts on macOS and Linux.
GitHub Codespaces also works: open the repo in a codespace and the dev container installs everything.

## Use a model

Copy `.env.example` to `.env` and pick a profile:

| Profile | What it calls | Settings |
|---|---|---|
| `offline` | nothing (B0 rules) | none |
| `local` | any OpenAI-compatible endpoint (vLLM, Ollama, ...) | `LOCAL_BASE_URL`, `LOCAL_API_KEY`, `LOCAL_MODEL` |
| `azure` | Azure OpenAI v1 endpoint with the standard OpenAI SDK | `AZURE_OPENAI_BASE_URL` (ends with `/openai/v1/`), `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` |

The results in this repo come from an open-weight 14B model served by vLLM on a single RTX 4090 workstation (`local`).

```bash
python -m sdagent run --id NEW-005 --profile local --explain   # one request, step by step
python -m sdagent batch --set incoming --profile local         # the 12 morning requests
python -m sdagent eval --config B3 --set dev --runs 3 --profile local
python -m sdagent summarize                                    # recompute every number from results/
```

## How it works

```mermaid
flowchart LR
  U["Request<br/>chat / web / email / phone"] --> S1["1 sanitize"] --> S2["2 understand<br/>(model)"] --> S3["3 correlate<br/>active incidents"] --> S4["4 retrieve<br/>Active KB"] --> S5["5 decide<br/>(model)"] --> S6["6 guard<br/>G1–G12"] --> S7["7 act<br/>ITSM tools"]
  S7 --> R["Reply with sources"]
  S7 --> C["Review console<br/>approve / reject"]
```

The order is fixed in code; the model only understands and decides. Rules, routing, priorities, required fields and keywords
live in `config/*.yaml`; prompts live in `prompts/*.md`. Every request leaves a full trace.
More: [docs/architecture.md](docs/architecture.md) (three diagrams, including the Azure target).

## Results

RESULTS_PLACEHOLDER

## Repository map

| Path | What it holds |
|---|---|
| `src/sdagent/` | the 7 steps, the B0 baseline, the CLI (about 1,650 lines, no file over 250) |
| `config/` | `routing.yaml` (categories, teams, priorities, fields, keywords) and `policies.yaml` (guard rules G1–G12) |
| `prompts/` | `understand.md`, `decide.md`, `llm_only.md` |
| `app/streamlit_app.py` | user chat, service desk review console, evaluation |
| `data/` | the original exercise package (unchanged, checksums in `data/SHA256SUMS`) and `data/synthetic/` (holdout and red team) |
| `eval/` | rubrics, label audit, checks, runner, scoring, report, frozen hashes, human review |
| `results/` | raw runs (`results/runs/*.jsonl`) and summaries |
| `docs/` | data assessment, success criteria, design decisions, architecture, evaluation, tuning log, Azure production, KPIs, cost model, demo script, AI tools usage, limitations |
| `tests/` | pytest |

## Assumptions and limits

The data assessment ([docs/data_assessment.md](docs/data_assessment.md)) lists the assumptions: the KB is the policy source,
historical labels are noisy examples, the priority mapping is assumed, and the user location must be asked for.
The main limits are in [docs/limitations.md](docs/limitations.md).

## Try a change yourself

1. Add a rule: edit `config/policies.yaml`, then `python -m sdagent run --id NEW-006 --explain`.
2. Change a priority rule in `config/routing.yaml` and re-run the evaluation: the rubric shows what breaks.
3. Add a KB article to `data/knowledge-base/` and re-run NEW-011: retrieval picks it up at start.
4. Compare `--profile offline` and `--profile local` on NEW-003 and NEW-012.
