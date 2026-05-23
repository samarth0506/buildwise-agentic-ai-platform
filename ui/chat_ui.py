"""
BuildWise chatbot UI (Streamlit).

All routing/HITL logic lives in middleware.router.handle_user_query.
This file only:
- collects user input
- calls the router
- renders the unified response shape

If middleware.router cannot be imported (e.g. during early scaffolding),
the page still loads with a safe inline fallback so the demo never crashes.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Callable

import streamlit as st

# ---------------------------------------------------------------------------
# Router import (with safe fallback)
# ---------------------------------------------------------------------------

_router_fn: Callable[[str], dict] | None = None
_router_import_error: str | None = None

try:
    from middleware.router import handle_user_query as _imported_router

    _router_fn = _imported_router
except Exception as exc:  # noqa: BLE001 - any import failure should not crash UI
    _router_fn = None
    _router_import_error = f"{type(exc).__name__}: {exc}"


def _fallback_response(query: str) -> dict:
    """Minimal stand-in if middleware.router is unavailable."""
    return {
        "final_response": (
            "Router unavailable — please make sure `middleware/router.py` is "
            "in place. Echoing your query so the UI keeps running:\n\n"
            f"> {query}"
        ),
        "intent": "general_inquiry",
        "agent_used": "Response Agent",
        "confidence": 0.5,
        "risk_level": "Medium",
        "risk_flags": [],
        "sources": [],
        "status": "sent_to_review",
        "ticket_id": f"HR-{random.randint(1000, 9999)}",
    }


def _run_pipeline(query: str) -> dict:
    if _router_fn is None:
        return _fallback_response(query)
    try:
        return _router_fn(query)
    except Exception as exc:  # noqa: BLE001
        return {
            **_fallback_response(query),
            "final_response": (
                f"Router raised {type(exc).__name__}: {exc}. "
                "A human reviewer will follow up."
            ),
        }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_risk_badge(risk_level: str) -> None:
    """Show a colored callout for the risk level."""
    level = (risk_level or "Low").title()
    if level == "High":
        st.error(f"Risk level: **{level}** — escalate or send for human review.")
    elif level == "Medium":
        st.warning(f"Risk level: **{level}** — monitor closely.")
    else:
        st.success(f"Risk level: **{level}** — safe to auto-respond.")


def _render_workflow_timeline(result: dict) -> None:
    """Show the 6-step agent workflow for the current response."""
    intent = result.get("intent", "unknown")
    agent = result.get("agent_used", "Response Agent")
    confidence = float(result.get("confidence", 0.0))
    risk_level = str(result.get("risk_level", "Low")).title()
    sent_to_review = result.get("status") == "sent_to_review"

    final_step = (
        "Human Review triggered"
        if sent_to_review
        else "Auto response delivered"
    )

    steps = [
        ("Query received",       "Captured from user input"),
        ("Intent classified",    intent),
        (f"{agent} invoked",     "Specialist agent generated draft"),
        ("Confidence checked",   f"{confidence:.0%}"),
        ("Risk checked",         risk_level),
        (final_step,             "sent_to_review" if sent_to_review else "auto_approved"),
    ]

    with st.expander("Agent Workflow Timeline", expanded=True):
        for idx, (title, detail) in enumerate(steps, start=1):
            cols = st.columns([1, 4, 4])
            cols[0].markdown(f"**Step {idx}**")
            cols[1].markdown(f"**{title}**")
            cols[2].markdown(f"`{detail}`")


def _render_response_cards(result: dict) -> None:
    """Render the full assistant message: response, metrics, risk, timeline."""
    st.markdown("**Final response**")
    with st.container(border=True):
        st.markdown(result["final_response"])

    _render_risk_badge(result.get("risk_level", "Low"))

    col1, col2, col3 = st.columns(3)
    col1.metric("Intent",     result.get("intent", "—"))
    col2.metric("Agent used", result.get("agent_used", "—"))
    col3.metric("Status",     result.get("status", "—"))

    confidence = float(result.get("confidence", 0.0))
    col4, col5, col6 = st.columns(3)
    col4.metric("Confidence", f"{confidence:.0%}")
    col5.metric("Risk level", str(result.get("risk_level", "Low")).title())
    col6.metric("Ticket ID",  result.get("ticket_id") or "—")

    st.caption("Confidence score")
    st.progress(min(max(confidence, 0.0), 1.0))

    if result.get("status") == "sent_to_review":
        st.warning(
            f"Response sent to Human Review Queue "
            f"(ticket `{result.get('ticket_id')}`). "
            "A reviewer will approve, reject, or edit it before it reaches the customer."
        )

    if result.get("risk_flags"):
        with st.expander("Risk flags"):
            for flag in result["risk_flags"]:
                st.markdown(f"- `{flag}`")

    if result.get("sources"):
        with st.expander("Sources"):
            for src in result["sources"]:
                st.markdown(f"- `{src}`")

    _render_workflow_timeline(result)


def _init_state() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def _render_history() -> None:
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                _render_response_cards(msg["content"])


def show_chat() -> None:
    """Render the BuildWise chatbot page."""
    st.header("BuildWise Assistant")
    st.caption(
        "Ask about construction status, property availability, documentation, "
        "maintenance issues, or escalations."
    )

    if _router_fn is None:
        st.error(
            f"middleware.router could not be loaded ({_router_import_error}). "
            "Using a fallback so the UI still renders."
        )

    _init_state()

    with st.sidebar:
        st.markdown("### Chat controls")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()
        st.caption(f"Messages in history: {len(st.session_state.chat_history)}")
        st.caption(f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    _render_history()

    prompt = st.chat_input("Type your question for BuildWise...")
    if not prompt:
        return

    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Routing through BuildWise agents..."):
            result = _run_pipeline(prompt)
        _render_response_cards(result)

    st.session_state.chat_history.append({"role": "assistant", "content": result})
