"""
BuildWise human review queue UI.

Uses middleware.hitl_service for queue persistence and middleware.audit_logger
for review-action audit trails. No sample/mock review data.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from middleware.hitl_service import (
    approve_response,
    edit_response,
    load_review_queue,
    reject_response,
)
from ui.backend_bridge import agent_name_for_intent, log_review_action, review_draft_text

REVIEWER = "streamlit_reviewer"


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _status_color(status: str) -> str:
    return {
        "pending": "orange",
        "approved": "green",
        "rejected": "red",
        "edited": "blue",
    }.get(status, "gray")


def _format_timestamp(item: dict[str, Any]) -> str:
    return str(item.get("timestamp") or item.get("created_at") or "—")


def _handle_approve(review_id: str) -> None:
    result = approve_response(review_id, reviewer=REVIEWER)
    if result.get("success"):
        log_review_action("review_approved", result.get("data", {}))
        st.success(f"Approved review `{review_id}`.")
    else:
        st.error(result.get("message", "Approval failed."))


def _handle_reject(review_id: str, reason: str = "") -> None:
    result = reject_response(review_id, reviewer=REVIEWER, reason=reason)
    if result.get("success"):
        log_review_action("review_rejected", result.get("data", {}))
        st.warning(f"Rejected review `{review_id}`.")
    else:
        st.error(result.get("message", "Rejection failed."))


def _handle_edit(review_id: str, edited_text: str) -> None:
    result = edit_response(review_id, edited_text, reviewer=REVIEWER)
    if result.get("success"):
        log_review_action("review_edited", result.get("data", {}))
        st.success(f"Saved edits for review `{review_id}`.")
    else:
        st.error(result.get("message", "Edit failed."))


def _render_item(item: dict[str, Any]) -> None:
    review_id = item.get("review_id", "UNKNOWN")
    status = item.get("status", "pending")
    intent = item.get("intent", "—")
    agent_label = agent_name_for_intent(intent)

    edit_key = f"edit_mode_{review_id}"
    draft_key = f"draft_text_{review_id}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.container(border=True):
        header_cols = st.columns([3, 1])
        header_cols[0].markdown(f"### Review `{review_id}`")
        header_cols[1].markdown(
            f":{_status_color(status)}[**{status.upper()}**]"
        )

        st.markdown(f"**User query:** {item.get('query', '—')}")

        meta_cols = st.columns(4)
        meta_cols[0].metric("Intent", intent)
        meta_cols[1].metric("Agent", agent_label)
        meta_cols[2].metric("Confidence", f"{float(item.get('confidence', 0)):.0%}")
        meta_cols[3].metric("Risk", str(item.get("risk_level", "—")).title())

        st.markdown("**Draft response**")
        if st.session_state[edit_key]:
            new_text = st.text_area(
                "Edit response",
                value=st.session_state.get(draft_key, review_draft_text(item)),
                key=draft_key,
                height=160,
                label_visibility="collapsed",
            )
            save_col, cancel_col = st.columns(2)
            if save_col.button("Save edits", key=f"save_{review_id}", type="primary"):
                _handle_edit(review_id, new_text)
                st.session_state[edit_key] = False
                st.rerun()
            if cancel_col.button("Cancel", key=f"cancel_{review_id}"):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            with st.container(border=True):
                st.markdown(review_draft_text(item) or "_No draft response._")

        ts_cols = st.columns(2)
        ts_cols[0].caption(f"Created: {_format_timestamp(item)}")
        if item.get("reviewed_at"):
            ts_cols[1].caption(f"Reviewed: {item['reviewed_at']}")

        if item.get("risk_flags"):
            with st.expander("Risk flags"):
                for flag in item["risk_flags"]:
                    st.markdown(f"- `{flag}`")

        if item.get("sources"):
            with st.expander("Sources"):
                for src in item["sources"]:
                    st.markdown(f"- `{src}`")

        if status == "pending":
            btn_cols = st.columns(3)
            if btn_cols[0].button("Approve", key=f"approve_{review_id}", type="primary"):
                _handle_approve(review_id)
                st.rerun()
            if btn_cols[1].button("Reject", key=f"reject_{review_id}"):
                _handle_reject(review_id)
                st.rerun()
            if btn_cols[2].button("Edit", key=f"edit_{review_id}"):
                st.session_state[edit_key] = True
                st.session_state[draft_key] = review_draft_text(item)
                st.rerun()
        elif item.get("rejection_reason"):
            st.caption(f"Rejection reason: {item['rejection_reason']}")


def show_review_queue() -> None:
    """Render the Human Review Queue page."""
    st.header("Human Review Queue")
    st.caption(
        "Cases flagged by the middleware risk engine appear here for human "
        "approval before they reach the customer."
    )

    reviews = load_review_queue()

    pending = [r for r in reviews if r.get("status") == "pending"]
    approved = [r for r in reviews if r.get("status") == "approved"]
    rejected = [r for r in reviews if r.get("status") == "rejected"]
    edited = [r for r in reviews if r.get("status") == "edited"]

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Pending", len(pending))
    kpi_cols[1].metric("Approved", len(approved))
    kpi_cols[2].metric("Rejected", len(rejected))
    kpi_cols[3].metric("Edited", len(edited))

    filter_choice = st.selectbox(
        "Filter by status",
        options=["pending", "all", "approved", "rejected", "edited"],
        index=0,
    )

    if filter_choice == "all":
        visible = reviews
    else:
        visible = [r for r in reviews if r.get("status") == filter_choice]

    if not reviews:
        st.info(
            "The review queue is empty. Submit a high-risk or low-confidence "
            "query in the Chatbot (e.g. “Why is Tower B delayed?”) to create one."
        )
        return

    if not visible:
        st.info(f"No `{filter_choice}` items in the review queue.")
        return

    for item in visible:
        _render_item(item)
