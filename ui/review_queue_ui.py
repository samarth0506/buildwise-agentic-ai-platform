"""
BuildWise human review queue UI — enterprise moderation dashboard.

Backend integration unchanged: middleware.hitl_service + audit_logger.
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
from ui.theme import (
    COLORS,
    chip_row,
    confidence_meter,
    empty_state,
    kpi_card,
    page_header,
    risk_variant,
    section_title,
)

REVIEWER = "streamlit_reviewer"


# ---------------------------------------------------------------------------
# Backend actions (unchanged)
# ---------------------------------------------------------------------------


def _handle_approve(review_id: str) -> None:
    result = approve_response(review_id, reviewer=REVIEWER)
    if result.get("success"):
        log_review_action("review_approved", result.get("data", {}))
        st.toast(f"Approved {review_id}", icon="✅")
    else:
        st.toast(result.get("message", "Approval failed."), icon="❌")


def _handle_reject(review_id: str, reason: str = "") -> None:
    result = reject_response(review_id, reviewer=REVIEWER, reason=reason)
    if result.get("success"):
        log_review_action("review_rejected", result.get("data", {}))
        st.toast(f"Rejected {review_id}", icon="⚠️")
    else:
        st.toast(result.get("message", "Rejection failed."), icon="❌")


def _handle_edit(review_id: str, edited_text: str) -> None:
    result = edit_response(review_id, edited_text, reviewer=REVIEWER)
    if result.get("success"):
        log_review_action("review_edited", result.get("data", {}))
        st.toast(f"Saved edits for {review_id}", icon="✅")
    else:
        st.toast(result.get("message", "Edit failed."), icon="❌")


# ---------------------------------------------------------------------------
# Filtering & sorting
# ---------------------------------------------------------------------------


def _format_timestamp(item: dict[str, Any]) -> str:
    return str(item.get("timestamp") or item.get("created_at") or "—")


def _risk_sort_key(item: dict[str, Any]) -> int:
    level = str(item.get("risk_level", "low")).lower()
    return {"high": 0, "medium": 1, "low": 2}.get(level, 3)


def _filter_and_sort(
    reviews: list[dict[str, Any]],
    search: str,
    status_filter: str,
    sort_by: str,
) -> list[dict[str, Any]]:
    visible = reviews

    if status_filter != "all":
        visible = [r for r in visible if r.get("status") == status_filter]

    if search.strip():
        q = search.lower().strip()
        visible = [
            r
            for r in visible
            if q in str(r.get("query", "")).lower()
            or q in str(r.get("review_id", "")).lower()
            or q in str(r.get("intent", "")).lower()
        ]

    if sort_by == "Highest risk":
        visible = sorted(visible, key=_risk_sort_key)
    elif sort_by == "Lowest confidence":
        visible = sorted(visible, key=lambda r: float(r.get("confidence", 0)))
    elif sort_by == "Highest confidence":
        visible = sorted(visible, key=lambda r: float(r.get("confidence", 0)), reverse=True)
    else:
        visible = list(reversed(visible))

    return visible


# ---------------------------------------------------------------------------
# Card rendering
# ---------------------------------------------------------------------------


def _status_chip_variant(status: str) -> str:
    return {
        "pending": "pending",
        "approved": "approved",
        "rejected": "rejected",
        "edited": "edited",
    }.get(status, "default")


def _render_item(item: dict[str, Any]) -> None:
    review_id = item.get("review_id", "UNKNOWN")
    status = item.get("status", "pending")
    intent = item.get("intent", "—")
    agent_label = agent_name_for_intent(intent)
    risk_level = str(item.get("risk_level", "low")).title()
    is_high_risk = str(item.get("risk_level", "")).lower() == "high"

    edit_key = f"edit_mode_{review_id}"
    draft_key = f"draft_text_{review_id}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    border_accent = COLORS["danger"] if is_high_risk else COLORS["accent"]
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, #121826 0%, #161f33 100%);
            border: 1px solid {COLORS['border']};
            border-left: 4px solid {border_accent};
            border-radius: 16px;
            padding: 0.25rem 0.5rem 0.5rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 12px 40px rgba(0,0,0,0.35);
        "></div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        header = st.columns([3, 1])
        header[0].markdown(f"#### `{review_id}`")
        chip_row([(status.upper(), _status_chip_variant(status))])

        if is_high_risk:
            st.markdown(
                f'<p style="color:{COLORS["danger"]};font-weight:600;font-size:0.85rem;margin:0 0 0.5rem;">🔴 High-risk case — priority review recommended</p>',
                unsafe_allow_html=True,
            )

        st.markdown(f"**User query:** {item.get('query', '—')}")

        chip_row([
            (agent_label, "agent"),
            (f"{float(item.get('confidence', 0)):.0%} confidence", "confidence"),
            (f"{risk_level} risk", risk_variant(item.get("risk_level", "low"))),
            (intent, "default"),
        ])

        confidence_meter(float(item.get("confidence", 0)))

        original = item.get("original_response") or ""
        edited = item.get("edited_response") or ""

        with st.expander("📄 Response details", expanded=status == "pending"):
            if edited and original and edited != original:
                comp1, comp2 = st.columns(2)
                with comp1:
                    st.markdown("**Original draft**")
                    st.markdown(original)
                with comp2:
                    st.markdown("**Edited version**")
                    st.markdown(edited)
            elif st.session_state[edit_key]:
                new_text = st.text_area(
                    "Edit response",
                    value=st.session_state.get(draft_key, review_draft_text(item)),
                    key=draft_key,
                    height=180,
                    label_visibility="collapsed",
                )
                save_col, cancel_col = st.columns(2)
                if save_col.button("💾 Save edits", key=f"save_{review_id}", type="primary"):
                    _handle_edit(review_id, new_text)
                    st.session_state[edit_key] = False
                    st.rerun()
                if cancel_col.button("Cancel", key=f"cancel_{review_id}"):
                    st.session_state[edit_key] = False
                    st.rerun()
            else:
                st.markdown(review_draft_text(item) or "_No draft response._")

        meta = st.columns(2)
        meta[0].caption(f"📅 Created: {_format_timestamp(item)}")
        if item.get("reviewed_at"):
            meta[1].caption(f"✅ Reviewed: {item['reviewed_at']}")

        if item.get("risk_flags"):
            with st.expander("⚠️ Risk flags"):
                for flag in item["risk_flags"]:
                    st.markdown(f"- `{flag}`")

        if status == "pending":
            st.markdown("##### Moderation actions")
            btn_cols = st.columns(3)
            if btn_cols[0].button(
                "✅ Approve",
                key=f"approve_{review_id}",
                type="primary",
                use_container_width=True,
            ):
                _handle_approve(review_id)
                st.rerun()
            if btn_cols[1].button(
                "❌ Reject",
                key=f"reject_{review_id}",
                use_container_width=True,
            ):
                _handle_reject(review_id)
                st.rerun()
            if btn_cols[2].button(
                "✏️ Edit",
                key=f"edit_{review_id}",
                use_container_width=True,
            ):
                st.session_state[edit_key] = True
                st.session_state[draft_key] = review_draft_text(item)
                st.rerun()
        elif item.get("rejection_reason"):
            st.caption(f"**Rejection reason:** {item['rejection_reason']}")


def show_review_queue() -> None:
    """Render the Human Review Queue page."""
    page_header(
        "Human Review Queue",
        "Professional moderation dashboard for HITL-flagged AI responses before customer delivery.",
        badge="Moderation",
    )

    reviews = load_review_queue()

    pending = [r for r in reviews if r.get("status") == "pending"]
    approved = [r for r in reviews if r.get("status") == "approved"]
    rejected = [r for r in reviews if r.get("status") == "rejected"]
    edited = [r for r in reviews if r.get("status") == "edited"]
    high_risk = [r for r in reviews if str(r.get("risk_level", "")).lower() == "high"]

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        kpi_card("Pending", len(pending), "⏳", COLORS["warning"])
    with k2:
        kpi_card("Approved", len(approved), "✅", COLORS["success"])
    with k3:
        kpi_card("Rejected", len(rejected), "❌", COLORS["danger"])
    with k4:
        kpi_card("Edited", len(edited), "✏️", COLORS["accent"])
    with k5:
        kpi_card("High risk", len(high_risk), "🔴", COLORS["danger"])

    section_title("Filters & search")

    f1, f2, f3 = st.columns([2, 1.2, 1])
    with f1:
        search = st.text_input(
            "🔍 Search",
            placeholder="Search by query, review ID, or intent…",
            label_visibility="collapsed",
        )
    with f2:
        status_filter = st.selectbox(
            "Status filter",
            options=["pending", "all", "approved", "rejected", "edited"],
            index=0,
            label_visibility="collapsed",
        )
    with f3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Newest", "Highest risk", "Lowest confidence", "Highest confidence"],
            index=0,
            label_visibility="collapsed",
        )

    st.markdown(
        f'<p style="color:{COLORS["text_muted"]};font-size:0.8rem;margin:0.5rem 0 1rem;">Filter chips: '
        f'<strong>pending</strong> · <strong>approved</strong> · <strong>rejected</strong> · <strong>edited</strong></p>',
        unsafe_allow_html=True,
    )

    if not reviews:
        empty_state(
            "📋",
            "Queue is empty",
            "Submit a high-risk query in the Chatbot — e.g. “Why is Tower B delayed?” — to populate the review queue.",
        )
        return

    visible = _filter_and_sort(reviews, search, status_filter, sort_by)

    if not visible:
        empty_state("🔍", "No matches", f"No reviews match your search or `{status_filter}` filter.")
        return

    section_title(f"Review cases ({len(visible)})", "Expand cards for details and moderation actions.")

    for item in visible:
        _render_item(item)
