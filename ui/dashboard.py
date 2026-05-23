"""
BuildWise dashboard UI.

Reads live data from middleware JSON stores:
- data/tickets.json
- data/review_queue.json
- data/audit_logs.json

All metrics and charts are computed dynamically — no placeholder samples.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

from middleware.audit_logger import get_audit_logs, get_audit_summary
from middleware.hitl_service import load_review_queue
from middleware.ticket_service import get_all_tickets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _count_chart(items: list[dict[str, Any]], key: str, label: str) -> pd.DataFrame:
    """Build a simple count DataFrame for st.bar_chart."""
    if not items:
        return pd.DataFrame({label: []})

    counts = Counter(
        str(item.get(key, "unknown")).strip().lower() or "unknown" for item in items
    )
    return pd.DataFrame(
        {label: list(counts.values())},
        index=list(counts.keys()),
    )


def _audit_action_label(entry: dict[str, Any]) -> str:
    """Derive a short action label for the audit log table."""
    if entry.get("event_type"):
        return str(entry["event_type"])
    if entry.get("review_required"):
        return "sent_to_review"
    return "query_processed"


def _audit_table_rows(logs: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Format audit logs for the recent activity table."""
    rows: list[dict[str, str]] = []
    for entry in reversed(logs[-25:]):
        rows.append(
            {
                "timestamp": str(entry.get("timestamp", "—")),
                "ticket_id": str(
                    entry.get("ticket_id") or entry.get("review_id") or "—"
                ),
                "action": _audit_action_label(entry),
                "status": str(entry.get("review_status", "—")),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------


def show_dashboard() -> None:
    """Render the BuildWise operations dashboard."""
    st.header("BuildWise Operations Dashboard")
    st.caption(
        "Live metrics from tickets, human review queue, and audit logs "
        "written by the middleware pipeline."
    )

    tickets = get_all_tickets()
    reviews = load_review_queue()
    logs = get_audit_logs()
    summary = get_audit_summary()

    pending_reviews = sum(1 for r in reviews if r.get("status") == "pending")
    approved_reviews = sum(1 for r in reviews if r.get("status") == "approved")
    rejected_reviews = sum(1 for r in reviews if r.get("status") == "rejected")

    escalations = sum(
        1
        for t in tickets
        if (t.get("intent") or "").lower() == "escalation"
        or (t.get("issue_type") or "").lower() == "escalation"
    )

    avg_confidence = summary.get("average_confidence", 0.0)
    if not avg_confidence and logs:
        avg_confidence = _safe_mean(
            [float(e.get("confidence", 0) or 0) for e in logs]
        )

    st.subheader("Key metrics")
    row1 = st.columns(4)
    row1[0].metric("Total tickets", len(tickets))
    row1[1].metric("Pending reviews", pending_reviews)
    row1[2].metric("Approved reviews", approved_reviews)
    row1[3].metric("Rejected reviews", rejected_reviews)

    row2 = st.columns(3)
    row2[0].metric("Escalations", escalations)
    row2[1].metric("Avg. confidence", f"{avg_confidence:.2f}")
    row2[2].metric("Audit log entries", len(logs))

    st.divider()

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.subheader("Review status distribution")
        if reviews:
            st.bar_chart(_count_chart(reviews, "status", "count"))
        else:
            st.info("No review queue entries yet.")

    with chart_cols[1]:
        st.subheader("Risk level distribution")
        risk_source = logs if logs else reviews
        if risk_source:
            st.bar_chart(_count_chart(risk_source, "risk_level", "count"))
        else:
            st.info("No risk data yet — run queries in the Chatbot.")

    chart_cols2 = st.columns(2)
    with chart_cols2[0]:
        st.subheader("Escalations (by issue type)")
        escalation_tickets = [
            t
            for t in tickets
            if (t.get("intent") or "").lower() == "escalation"
            or (t.get("issue_type") or "").lower() == "escalation"
        ]
        if escalation_tickets:
            st.bar_chart(_count_chart(escalation_tickets, "issue_type", "count"))
        else:
            st.info("No escalation tickets recorded yet.")

    with chart_cols2[1]:
        st.subheader("Ticket categories (intent)")
        if tickets:
            st.bar_chart(_count_chart(tickets, "intent", "count"))
        else:
            st.info("No support tickets yet.")

    st.divider()

    st.subheader("Recent audit log")
    if logs:
        st.dataframe(
            pd.DataFrame(_audit_table_rows(logs)),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No audit log entries yet. Interactions are logged when you use the Chatbot.")

    with st.expander("All tickets"):
        if tickets:
            st.dataframe(
                pd.DataFrame(tickets),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No tickets in data/tickets.json.")

    with st.expander("All review queue items"):
        if reviews:
            st.dataframe(
                pd.DataFrame(reviews),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No items in data/review_queue.json.")
