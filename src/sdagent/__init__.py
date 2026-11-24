"""IT service desk triage agent prototype."""
import os
from pathlib import Path

# Repo root. The package is installed in editable mode (pip install -e .), so this points at the checkout.
ROOT = Path(os.getenv("SDAGENT_ROOT", Path(__file__).resolve().parents[2]))
