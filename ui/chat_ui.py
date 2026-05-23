"""
BuildWise chatbot UI (Streamlit).

Routes every user message through middleware.router.handle_user_query and
renders the unified backend response. No mock agent logic lives here.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from middleware.router import handle_user_query
from ui.backend_bridge import normalize_router_result

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _run_pipeline(query: str) -> dict:
    """Call the backend router and normalize the result for display."""
    try:
        raw = handle_user_query(query)
        return normalize_router_result(raw)
    except Exception as exc:  # noqa: BLE001 — keep chat usable on unexpected errors
        return normalize_router_result(
            {
                "final_response": (
                    "The BuildWise router could not process your request. "
                    f"Error: {type(exc).__name__}: {exc}"
                ),
                "intent": "error",
                "agent_used": "Router",
                "confidence": 0.0,
                "risk_flags": ["router_error"],
                "risk_level": "high",
                "sources": [],
                "status": "error",
                "review_required": True,
            }
        )


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
    """Show the 5-step agent workflow for the current response."""
    intent = result.get("intent", "unknown")
    agent = result.get("agent_used", "Response Agent")
    risk_level = str(result.get("risk_level", "Low")).title()
    sent_to_review = result.get("status") == "sent_to_review"

    final_step = "HITL Triggered" if sent_to_review else "Auto Approved"

    steps = [
        "Query Received",
        f"Intent Classified ({intent})",
        f"Agent Invoked ({agent})",
        f"Risk Evaluation ({risk_level})",
        final_step,
    ]

    with st.expander("Agent Workflow Timeline", expanded=True):
        for step in steps:
            st.markdown(f"✔ {step}")


def _display_id(result: dict) -> str:
    """Prefer support ticket ID; fall back to review ID."""
    return result.get("ticket_id") or result.get("review_id") or "—"


def _render_response_cards(result: dict) -> None:
    """Render the full assistant message: response, metrics, risk, timeline."""
    st.markdown("**Final response**")
    with st.container(border=True):
        st.markdown(result["final_response"])

    _render_risk_badge(result.get("risk_level", "Low"))

    col1, col2, col3 = st.columns(3)
    col1.metric("Intent", result.get("intent", "—"))
    col2.metric("Agent used", result.get("agent_used", "—"))
    col3.metric("Status", result.get("status", "—"))

    confidence = float(result.get("confidence", 0.0))
    col4, col5, col6 = st.columns(3)
    col4.metric("Confidence", f"{confidence:.0%}")
    col5.metric("Risk level", str(result.get("risk_level", "Low")).title())
    col6.metric("Ticket / Review ID", _display_id(result))

    st.caption("Confidence score")
    st.progress(min(max(confidence, 0.0), 1.0))

    if result.get("status") == "sent_to_review":
        review_ref = result.get("review_id") or result.get("ticket_id") or "pending"
        st.warning(f"⚠️ Sent to Human Review Queue (ref: `{review_ref}`)")

    if result.get("risk_flags"):
        with st.expander("Risk flags"):
            for flag in result["risk_flags"]:
                st.markdown(f"- `{flag}`")

    if result.get("sources"):
        with st.expander("Sources"):
            for src in result["sources"]:
                st.markdown(f"- `{src}`")

    if result.get("audit_log_id"):
        st.caption(f"Audit log: `{result['audit_log_id']}`")

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
        "maintenance issues, or escalations. Responses are routed through the "
        "BuildWise middleware pipeline."
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
