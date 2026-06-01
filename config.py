"""
BuildWise central configuration — OpenAI, LLM toggles, and confidence thresholds.

Loads ``.env`` from the project root (and optionally the process cwd).
Call ``reload_config()`` before LLM calls so Streamlit picks up the latest ``.env``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_API_KEY = ""
ENABLE_LLM_RESPONSES = True
CONFIDENCE_THRESHOLD = 0.70


def _parse_enable_llm(raw: str) -> bool:
    return raw.strip().lower() in ("true", "1", "yes", "on")


def reload_config() -> None:
    """Reload environment variables from ``.env`` (project root, then cwd)."""
    global OPENAI_MODEL, OPENAI_API_KEY, ENABLE_LLM_RESPONSES, CONFIDENCE_THRESHOLD

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    load_dotenv(override=True)

    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
    ENABLE_LLM_RESPONSES = _parse_enable_llm(os.getenv("ENABLE_LLM_RESPONSES", "true"))

    try:
        CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.70"))
    except ValueError:
        CONFIDENCE_THRESHOLD = 0.70
    CONFIDENCE_THRESHOLD = max(0.0, min(1.0, CONFIDENCE_THRESHOLD))


# Initial load at import
reload_config()
