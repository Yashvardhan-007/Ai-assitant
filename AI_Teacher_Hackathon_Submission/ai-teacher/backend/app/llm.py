"""
llm.py — Thin wrapper around the Anthropic Claude API.

Design goal: the whole application must still run and produce a working
demo even if no ANTHROPIC_API_KEY is configured (useful for offline testing
and for judges who just want to click around). When a key IS present, every
function below automatically switches to real LLM-generated content instead
of the rule-based fallback.

Set your key as an environment variable before starting the server:
    export ANTHROPIC_API_KEY="sk-ant-..."
Optionally also:
    export ANTHROPIC_MODEL="claude-sonnet-4-6"   (default used below)
"""

import os
import json
import re

try:
    import anthropic
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()

_client = None
if _HAS_SDK and API_KEY:
    _client = anthropic.Anthropic(api_key=API_KEY)


def llm_available() -> bool:
    return _client is not None


def _call(system: str, prompt: str, max_tokens: int = 1500) -> str:
    """Raw text completion. Raises if the client isn't configured —
    callers should always check llm_available() first or catch the error."""
    if _client is None:
        raise RuntimeError("LLM not configured (no ANTHROPIC_API_KEY)")
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "\n".join(parts)


def _extract_json(text: str):
    """LLMs sometimes wrap JSON in prose or code fences — pull the JSON out."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # find first { ... last } as a safety net
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    return json.loads(text)


def call_json(system: str, prompt: str, max_tokens: int = 2000):
    """Call the LLM and parse a JSON object out of the response."""
    raw = _call(system, prompt, max_tokens=max_tokens)
    return _extract_json(raw)


def call_text(system: str, prompt: str, max_tokens: int = 1200) -> str:
    return _call(system, prompt, max_tokens=max_tokens).strip()
