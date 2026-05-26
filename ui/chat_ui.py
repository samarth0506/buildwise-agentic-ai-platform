"""
BuildWise chatbot UI (Streamlit).

Routes every user message through middleware.router.handle_user_query.
Visual layer only — backend integration unchanged.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from middleware.router import handle_user_query
from ui.backend_bridge import normalize_router_result
from ui.theme import (
    alert_banner,
    assistant_response_block,
    chip_row,
    confidence_meter,
    empty_state,
    page_header,
    risk_variant,
    user_bubble,
    workflow_timeline,
)


# ---------------------------------------------------------------------------
# Pipeline (unchanged backend integration)
# ---------------------------------------------------------------------------


def _run_pipeline(query: str) -> dict:
    """Call the backend router and normalize the result for display."""
    try:
        raw = handle_user_query(query)
        return normalize_router_result(raw)
    except Exception as exc:  # noqa: BLE001
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


def _build_workflow_steps(result: dict) -> list[tuple[str, bool]]:
    """Six-step enterprise workflow visualization."""
    intent = result.get("intent", "unknown")
    agent = result.get("agent_used", "Response Agent")
    sent_to_review = result.get("status") == "sent_to_review"
    has_sources = bool(result.get("sources"))
    final_label = "HITL Triggered" if sent_to_review else "Auto Approved"

    return [
        ("Query Received", True),
        (f"Intent Classified — {intent}", True),
        (f"Agent Selected — {agent}", True),
        (
            "RAG Retrieval Completed" if has_sources else "RAG Retrieval — internal knowledge",
            True,
        ),
        (
            f"Confidence Evaluated — {float(result.get('confidence', 0)):.0%}",
            True,
        ),
        (final_label, True),
    ]


def _response_chips(result: dict) -> None:
    """Agent, confidence, risk, and HITL badges."""
    chips: list[tuple[str, str]] = [
        (f"🤖 {result.get('agent_used', 'Agent')}", "agent"),
        (f"📊 {float(result.get('confidence', 0)):.0%} confidence", "confidence"),
        (f"⚡ {str(result.get('risk_level', 'Low')).title()} risk", risk_variant(result.get("risk_level", "low"))),
    ]
    if result.get("status") == "sent_to_review":
        chips.append(("⚠️ HITL Review", "hitl"))
    elif result.get("status") == "auto_approved":
        chips.append(("✅ Auto Approved", "approved"))
    chip_row(chips)


def _display_id(result: dict) -> str:
    return result.get("ticket_id") or result.get("review_id") or "—"


def _render_response_cards(result: dict, timestamp: str = "") -> None:
    """Render polished assistant response with metrics and workflow."""
    _response_chips(result)

    if timestamp:
        st.caption(f"🕐 {timestamp}")

    assistant_response_block(result.get("final_response", ""))

    if result.get("status") == "sent_to_review":
        ref = result.get("review_id") or result.get("ticket_id") or "pending"
        alert_banner(f"⚠️ Sent to Human Review Queue — reference `{ref}`", "warning")

    confidence_meter(float(result.get("confidence", 0.0)))

    m1, m2, m3 = st.columns(3)
    m1.metric("Intent", result.get("intent", "—"))
    m2.metric("Status", str(result.get("status", "—")).replace("_", " ").title())
    m3.metric("Ticket / Review ID", _display_id(result))

    with st.expander("🔧 Technical details", expanded=False):
        d1, d2 = st.columns(2)
        d1.markdown(f"**Agent:** {result.get('agent_used', '—')}")
        d1.markdown(f"**Risk level:** {result.get('risk_level', '—')}")
        d2.markdown(f"**Audit log:** `{result.get('audit_log_id') or '—'}`")
        d2.markdown(f"**Review ID:** `{result.get('review_id') or '—'}`")

        if result.get("risk_flags"):
            st.markdown("**Risk flags**")
            for flag in result["risk_flags"]:
                st.markdown(f"- `{flag}`")

        if result.get("sources"):
            st.markdown("**Sources**")
            for src in result["sources"]:
                st.markdown(f"- `{src}`")

        st.download_button(
            label="📋 Copy response",
            data=result.get("final_response", ""),
            file_name="buildwise_response.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with st.expander("🔄 Agent workflow timeline", expanded=True):
        workflow_timeline(_build_workflow_steps(result))


def _init_state() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def _render_history() -> None:
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            user_bubble(msg["content"])
            if msg.get("timestamp"):
                st.markdown(
                    f'<p style="text-align:right;color:#64748b;font-size:0.72rem;margin:-0.25rem 0 0.75rem;">{msg["timestamp"]}</p>',
                    unsafe_allow_html=True,
                )
        else:
            with st.chat_message("assistant", avatar="🤖"):
                _render_response_cards(msg["content"], msg.get("timestamp", ""))


def show_chat() -> None:
    """Render the BuildWise chatbot page."""
    page_header(
        "BuildWise Assistant",
        "Enterprise AI assistant with dynamic agent routing, RAG retrieval, and human-in-the-loop safeguards.",
        badge="Online",
    )

    _init_state()

    with st.sidebar:
        st.markdown("##### Session controls")
        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state.chat_history = []
            st.toast("Conversation cleared", icon="✅")
            st.rerun()
        st.caption(f"Messages: **{len(st.session_state.chat_history)}**")
        st.caption(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if not st.session_state.chat_history:
        empty_state(
            "💬",
            "Start a conversation",
            "Ask about tower status, KYC documents, maintenance issues, property listings, or escalations.",
        )

    _render_history()

    prompt = st.chat_input("Ask BuildWise anything — construction, docs, maintenance, property…")
    if not prompt:
        return

    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.chat_history.append(
        {"role": "user", "content": prompt, "timestamp": ts}
    )
    user_bubble(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔄 Routing through agents · evaluating risk · checking HITL…"):
            result = _run_pipeline(prompt)
        _render_response_cards(result, ts)

    st.session_state.chat_history.append(
        {"role": "assistant", "content": result, "timestamp": ts}
    )

    if result.get("status") == "sent_to_review":
        st.toast("Response queued for human review", icon="⚠️")
    else:
        st.toast("Response delivered", icon="✅")
