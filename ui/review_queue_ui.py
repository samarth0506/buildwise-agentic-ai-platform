"""
BuildWise human review queue UI.

Reads/writes data/review_queue.json. If the file is missing or empty,
shows sample pending reviews so the page is never blank.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import streamlit as st

DATA_DIR = "data"
REVIEW_FILE = os.path.join(DATA_DIR, "review_queue.json")

SAMPLE_REVIEWS: list[dict[str, Any]] = [
    {
        "ticket_id": "T-1001",
        "query": "Why is Tower B delayed?",
        "draft_response": (
            "Tower B is delayed by 3–4 weeks due to material delivery issues. "
            "The site team is targeting recovery within the next sprint."
        ),
        "confidence": 0.62,
        "risk_level": "high",
        "status": "pending",
        "intent": "construction_status",
        "agent_used": "construction_agent",
        "created_at": "2026-05-22 14:05",
    },
    {
        "ticket_id": "T-1002",
        "query": "I want a refund for my booking — this is urgent.",
        "draft_response": (
            "We understand your concern. A senior relationship manager will "
            "contact you within 24 hours to review the refund request."
        ),
        "confidence": 0.48,
        "risk_level": "high",
        "status": "pending",
        "intent": "escalation",
        "agent_used": "escalation_agent",
        "created_at": "2026-05-22 16:18",
    },
    {
        "ticket_id": "T-1003",
        "query": "Is 3BHK available in Tower C with parking?",
        "draft_response": (
            "Yes, 3BHK units are available in Tower C with covered parking. "
            "Pricing starts at approximately 1.1 Cr."
        ),
        "confidence": 0.69,
        "risk_level": "medium",
        "status": "pending",
        "intent": "property_inquiry",
        "agent_used": "property_agent",
        "created_at": "2026-05-22 17:42",
    },
]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_data_file() -> None:
    """Create data/review_queue.json with sample content if missing/empty."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(REVIEW_FILE) or os.path.getsize(REVIEW_FILE) == 0:
        with open(REVIEW_FILE, "w", encoding="utf-8") as fh:
            json.dump(SAMPLE_REVIEWS, fh, indent=2)


def _load_reviews() -> list[dict[str, Any]]:
    _ensure_data_file()
    try:
        with open(REVIEW_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list) and data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return list(SAMPLE_REVIEWS)


def _save_reviews(reviews: list[dict[str, Any]]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REVIEW_FILE, "w", encoding="utf-8") as fh:
        json.dump(reviews, fh, indent=2)


def _update_review(ticket_id: str, **changes: Any) -> None:
    reviews = _load_reviews()
    for item in reviews:
        if item.get("ticket_id") == ticket_id:
            item.update(changes)
            item["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break
    _save_reviews(reviews)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _status_color(status: str) -> str:
    return {
        "pending": "orange",
        "approved": "green",
        "rejected": "red",
        "edited": "blue",
    }.get(status, "gray")


def _render_item(item: dict[str, Any]) -> None:
    ticket_id = item.get("ticket_id", "UNKNOWN")
    status = item.get("status", "pending")
    edit_key = f"edit_mode_{ticket_id}"
    draft_key = f"draft_text_{ticket_id}"

    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.container(border=True):
        header_cols = st.columns([3, 1])
        header_cols[0].markdown(f"### Ticket `{ticket_id}`")
        header_cols[1].markdown(
            f":{_status_color(status)}[**{status.upper()}**]"
        )

        st.markdown(f"**User query:** {item.get('query', '—')}")

        meta_cols = st.columns(4)
        meta_cols[0].metric("Intent", item.get("intent", "—"))
        meta_cols[1].metric("Agent", item.get("agent_used", "—"))
        meta_cols[2].metric("Confidence", f"{float(item.get('confidence', 0)):.2f}")
        meta_cols[3].metric("Risk", str(item.get("risk_level", "—")).title())

        st.markdown("**Draft response**")
        if st.session_state[edit_key]:
            new_text = st.text_area(
                "Edit response",
                value=st.session_state.get(draft_key, item.get("draft_response", "")),
                key=draft_key,
                height=140,
                label_visibility="collapsed",
            )
            save_col, cancel_col = st.columns(2)
            if save_col.button("Save edits", key=f"save_{ticket_id}", type="primary"):
                _update_review(
                    ticket_id,
                    draft_response=new_text,
                    status="edited",
                )
                st.session_state[edit_key] = False
                st.success(f"Saved edits for {ticket_id}.")
                st.rerun()
            if cancel_col.button("Cancel", key=f"cancel_{ticket_id}"):
                st.session_state[edit_key] = False
                st.rerun()
        else:
            with st.container(border=True):
                st.markdown(item.get("draft_response", "_No draft response._"))

        st.caption(f"Created: {item.get('created_at', '—')}")

        if status == "pending":
            btn_cols = st.columns(3)
            if btn_cols[0].button("Approve", key=f"approve_{ticket_id}", type="primary"):
                _update_review(ticket_id, status="approved")
                st.success(f"Approved {ticket_id}.")
                st.rerun()
            if btn_cols[1].button("Reject", key=f"reject_{ticket_id}"):
                _update_review(ticket_id, status="rejected")
                st.warning(f"Rejected {ticket_id}.")
                st.rerun()
            if btn_cols[2].button("Edit", key=f"edit_{ticket_id}"):
                st.session_state[edit_key] = True
                st.session_state[draft_key] = item.get("draft_response", "")
                st.rerun()
        else:
            if st.button("Reopen for review", key=f"reopen_{ticket_id}"):
                _update_review(ticket_id, status="pending")
                st.rerun()


def show_review_queue() -> None:
    """Render the Human Review Queue page."""
    st.header("Human Review Queue")
    st.caption(
        "Low-confidence or high-risk draft responses appear here for a human "
        "reviewer to approve, reject, or edit before they reach the customer."
    )

    reviews = _load_reviews()

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

    if not visible:
        st.info(f"No `{filter_choice}` items in the review queue.")
        return

    for item in visible:
        _render_item(item)
