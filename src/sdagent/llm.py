"""Model client for the two model steps (understand, decide) and for B1.
One OpenAI-compatible client covers local vLLM and Azure OpenAI (v1 endpoint), so switching is a config change.
Structured output: json_schema first; then JSON mode with pydantic validation and one retry with the error.
If that still fails the caller gets None and fails closed to a person (human_triage).
"""
from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from . import ROOT
from .data import PROMPTS


def strict_schema(model: type[BaseModel], enums: dict[str, list[str]] | None = None) -> dict:
    """Pydantic schema in the strict form both vLLM and Azure accept: refs inlined, no extra keys, all required."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def fix(node):
        if isinstance(node, list):
            return [fix(x) for x in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return fix(defs[node["$ref"].split("/")[-1]])
        node = {k: fix(v) for k, v in node.items() if k not in ("title", "default")}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        return node

    schema = fix(raw)
    for field, values in (enums or {}).items():
        prop = schema["properties"][field]
        (prop["items"] if prop.get("type") == "array" else prop)["enum"] = values
    return schema


def render(name: str, **values) -> tuple[str, str]:
    """Load prompts/<name>.md, fill {{placeholders}}, split into the system and user messages."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", str(value))
    system, user = text.split("# user", 1)
    return system.replace("# system", "", 1).strip(), user.strip()


class LLM:
    def __init__(self, profile: str):
        load_dotenv(ROOT / ".env")
        self.profile = profile
        if profile == "local":
            base, key, self.model = os.getenv("LOCAL_BASE_URL"), os.getenv("LOCAL_API_KEY", "not-needed"), os.getenv("LOCAL_MODEL")
        elif profile == "azure":
            base, key, self.model = (os.getenv("AZURE_OPENAI_BASE_URL"), os.getenv("AZURE_OPENAI_API_KEY"),
                                     os.getenv("AZURE_OPENAI_DEPLOYMENT"))
        else:
            raise ValueError("the offline profile has no model")
        if not (base and key and self.model):
            raise ValueError(f"missing settings for profile '{profile}' in .env")
        self.client = OpenAI(base_url=base, api_key=key, timeout=90, max_retries=1)

    def chat(self, messages: list[dict], response_format: dict, max_tokens: int, meta: dict) -> str:
        t0 = time.perf_counter()
        r = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0,
                                                max_tokens=max_tokens, response_format=response_format)
        meta["calls"] += 1
        meta["ms"] += int((time.perf_counter() - t0) * 1000)
        if r.usage:
            meta["prompt_tokens"] += r.usage.prompt_tokens
            meta["completion_tokens"] += r.usage.completion_tokens
        return r.choices[0].message.content or ""

    def structured(self, system: str, user: str, model: type[BaseModel], enums: dict | None = None,
                   max_tokens: int = 1000) -> tuple[BaseModel | None, dict]:
        meta = {"calls": 0, "ms": 0, "prompt_tokens": 0, "completion_tokens": 0, "mode": "json_schema", "errors": []}
        schema = strict_schema(model, enums)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        attempts = [{"type": "json_schema", "json_schema": {"name": model.__name__, "schema": schema, "strict": True}},
                    {"type": "json_object"}, {"type": "json_object"}]
        for i, fmt in enumerate(attempts):
            meta["mode"] = fmt["type"]
            try:
                text = self.chat(messages, fmt, max_tokens, meta)
                return model.model_validate_json(text), meta
            except Exception as e:  # unsupported json_schema, invalid JSON or wrong fields
                meta["errors"].append(f"{fmt['type']}: {str(e)[:200]}")
                if i == 0:
                    messages = messages + [{"role": "user", "content": "Return only one JSON object that matches this "
                                            f"JSON schema: {json.dumps(schema)}"}]
                else:
                    messages = messages + [{"role": "user", "content": f"That answer was not valid: {str(e)[:300]}. "
                                            "Return only the corrected JSON object."}]
        return None, meta
