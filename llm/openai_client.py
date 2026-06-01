"""
BuildWise OpenAI client — grounded response generation from retrieved context.

Requires ``OPENAI_API_KEY`` in ``.env``. Uses ``OPENAI_MODEL`` (default: gpt-4o-mini).
Returns ``None`` on missing key or API failure so callers can use rule-based fallback.
"""

from __future__ import annotations

import logging
import sys
import traceback
from typing import Optional

try:
    import truststore as ts

    ts.inject_into_ssl()
except ImportError:
    pass

from config import reload_config

logger = logging.getLogger(__name__)

_client = None


def _llm_log(message: str) -> None:
    """Print to terminal (Streamlit console) and log at INFO."""
    line = f"[LLM] {message}"
    print(line, flush=True)
    logger.info(line)


def _get_client(api_key: str):
    """Lazy-create OpenAI client when API key is present."""
    global _client
    if not api_key:
        return None
    if _client is not None:
        return _client
    try:
        from openai import OpenAI

        _client = OpenAI(api_key=api_key)
        return _client
    except Exception as exc:  # noqa: BLE001
        _llm_log(f"Could not initialize OpenAI client: {exc}")
        traceback.print_exc(file=sys.stderr)
        return None


def _build_system_prompt(agent_name: str, intent: str) -> str:
    return f"""You are the {agent_name} for BuildWise, a construction and real-estate customer support platform.
Current intent category: {intent.replace("_", " ")}.

Rules (strict):
- Answer ONLY using facts from the RETRIEVED CONTEXT below. Do not invent prices, dates, legal outcomes, refunds, or compensation.
- Do not promise refunds, legal resolutions, possession dates, or compensation unless explicitly stated in the context.
- If the context is empty or insufficient to answer safely, say clearly that a human reviewer will follow up — do not guess.
- For legal, payment dispute, escalation, or safety topics, recommend human review even if partial context exists.
- Write in clear, professional, customer-friendly plain text (no markdown headers unless the context uses them).
- Keep responses concise (roughly 3–8 sentences unless the user asked for a detailed list).
- Do not mention OpenAI, models, or internal systems."""


def _build_user_prompt(
    user_query: str,
    retrieved_context: str,
    agent_name: str,
    intent: str,
) -> str:
    context_block = retrieved_context.strip() if retrieved_context else ""
    if not context_block:
        context_block = "(No retrieved context available.)"

    return f"""USER QUESTION:
{user_query.strip()}

RETRIEVED CONTEXT:
{context_block}

Using only the retrieved context, write a helpful reply for the customer.
Agent: {agent_name} | Intent: {intent}"""


def generate_llm_response(
    user_query: str,
    retrieved_context: str,
    agent_name: str,
    intent: str,
) -> Optional[str]:
    """
    Generate a grounded customer reply via OpenAI.

    Returns:
        Plain-text response on success, or ``None`` if LLM is disabled, key is missing,
        or the API call fails (caller should use rule-based fallback).
    """
    reload_config()
    from config import ENABLE_LLM_RESPONSES, OPENAI_API_KEY, OPENAI_MODEL

    _llm_log("generate_llm_response called")
    _llm_log(f"ENABLE_LLM_RESPONSES={ENABLE_LLM_RESPONSES}")
    _llm_log(f"API key found={bool(OPENAI_API_KEY)}")
    _llm_log(f"model={OPENAI_MODEL}")

    if not ENABLE_LLM_RESPONSES:
        _llm_log("fallback used because: ENABLE_LLM_RESPONSES is False")
        return None

    if not OPENAI_API_KEY:
        _llm_log("fallback used because: OPENAI_API_KEY is missing or empty")
        return None

    client = _get_client(OPENAI_API_KEY)
    if client is None:
        _llm_log("fallback used because: OpenAI client could not be created")
        return None

    if not (user_query or "").strip():
        _llm_log("fallback used because: user_query is empty")
        return None

    system_prompt = _build_system_prompt(agent_name, intent)
    user_prompt = _build_user_prompt(user_query, retrieved_context, agent_name, intent)

    try:
        _llm_log("calling OpenAI...")
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        text = (completion.choices[0].message.content or "").strip()
        if text:
            _llm_log("OpenAI response generated successfully")
            return text
        _llm_log("fallback used because: OpenAI returned empty content")
        return None
    except Exception as exc:  # noqa: BLE001
        _llm_log(f"fallback used because: API error — {type(exc).__name__}: {exc}")
        traceback.print_exc(file=sys.stderr)
        return None
