# Shortcuts for macOS / Linux. On Windows, run the python commands directly (see README).
PY ?= .venv/bin/python

setup:
	python3 -m venv .venv && $(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

batch:
	$(PY) -m sdagent batch --set incoming --profile offline

app:
	$(PY) -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8601

summary:
	$(PY) -m sdagent summarize

.PHONY: setup test batch app summary
