"""
BuildWise dashboard UI.

Reads sample data from data/tickets.json, data/audit_logs.json,
and data/review_queue.json. Falls back to in-memory samples if any
file is missing or malformed.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

DATA_DIR = "data"
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
LOGS_FILE = os.path.join(DATA_DIR, "audit_logs.json")
REVIEW_FILE = os.path.join(DATA_DIR, "review_queue.json")

SAMPLE_TICKETS: list[dict[str, Any]] = [
    {
        "ticket_id": "T-1001",
        "query": "Why is Tower B delayed?",
        "intent": "construction_status",
        "agent_used": "construction_agent",
        "confidence": 0.62,
        "risk_level": "high",
        "status": "sent_to_review",
        "created_at": "2026-05-22 14:05",
    },
    {
        "ticket_id": "T-1002",
        "query": "I want a refund for my booking — this is urgent.",
        "intent": "escalation",
        "agent_used": "escalation_agent",
        "confidence": 0.48,
        "risk_level": "high",
        "status": "escalated",
        "created_at": "2026-05-22 16:18",
    },
    {
        "ticket_id": "T-1003",
        "query": "Is 3BHK available in Tower C with parking?",
        "intent": "property_inquiry",
        "agent_used": "property_agent",
        "confidence": 0.88,
        "risk_level": "low",
        "status": "answered",
        "created_at": "2026-05-22 17:42",
    },
    {
        "ticket_id": "T-1004",
        "query": "Water leakage in flat 502, Tower A.",
        "intent": "maintenance_issue",
        "agent_used": "maintenance_agent",
        "confidence": 0.81,
        "risk_level": "medium",
        "status": "answered",
        "created_at": "2026-05-23 09:11",
    },
    {
        "ticket_id": "T-1005",
        "query": "Status of KYC documents submitted last week.",
        "intent": "documentation_support",
        "agent_used": "documentation_agent",
        "confidence": 0.79,
        "risk_level": "low",
        "status": "answered",
        "created_at": "2026-05-23 10:34",
    },
    {
        "ticket_id": "T-1006",
        "query": "When will Tower A finishing work complete?",
        "intent": "construction_status",
        "agent_used": "construction_agent",
        "confidence": 0.85,
        "risk_level": "low",
        "status": "answered",
        "created_at": "2026-05-23 11:02",
    },
]

SAMPLE_LOGS: list[dict[str, Any]] = [
    {
        "timestamp": "2026-05-23 09:11",
        "ticket_id": "T-1004",
        "agent": "maintenance_agent",
        "action": "draft_response_generated",
    },
    {
        "timestamp": "2026-05-23 09:11",
        "ticket_id": "T-1004",
        "agent": "response_agent",
        "action": "response_sent",
    },
    {
        "timestamp": "2026-05-23 10:34",
        "ticket_id": "T-1005",
        "agent": "documentation_agent",
        "action": "draft_response_generated",
    },
    {
        "timestamp": "2026-05-22 14:06",
        "ticket_id": "T-1001",
        "agent": "confidence_check",
        "action": "flagged_for_human_review",
    },
    {
        "timestamp": "2026-05-22 16:19",
        "ticket_id": "T-1002",
        "agent": "escalation_agent",
        "action": "escalated_to_manager",
    },
]


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Load a JSON list from disk, returning fallback on any problem."""
    _ensure_data_dir()
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(fallback, fh, indent=2)
        except OSError:
            pass
        return list(fallback)

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list) and data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return list(fallback)


# ---------------------------------------------------------------------------
# Chart helpers — convert counts to DataFrame for st.bar_chart
# ---------------------------------------------------------------------------

def _count_chart(items: list[dict[str, Any]], key: str, label: str) -> pd.DataFrame:
    counts = Counter(
        str(item.get(key, "unknown")).strip().lower() or "unknown" for item in items
    )
    df = pd.DataFrame(
        {label: list(counts.values())},
        index=list(counts.keys()),
    )
    df.index.name = key
    return df


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

def show_dashboard() -> None:
    """Render the BuildWise dashboard page."""
    st.header("BuildWise Operations Dashboard")
    st.caption(
        "Live view of tickets, agent activity, and human review queue. "
        "Uses sample data if data files are not yet populated."
    )

    tickets = _load_json(TICKETS_FILE, SAMPLE_TICKETS)
    logs = _load_json(LOGS_FILE, SAMPLE_LOGS)
    reviews = _load_json(REVIEW_FILE, [])

    total_tickets = len(tickets)
    pending_reviews = sum(1 for r in reviews if r.get("status") == "pending")
    escalations = sum(
        1
        for t in tickets
        if t.get("intent") == "escalation" or t.get("status") == "escalated"
    )
    avg_conf = _safe_mean(
        [float(t.get("confidence", 0) or 0) for t in tickets]
    )

    st.subheader("Key metrics")
    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Total tickets", total_tickets)
    kpi_cols[1].metric("Pending reviews", pending_reviews)
    kpi_cols[2].metric("Escalations", escalations)
    kpi_cols[3].metric("Avg. confidence", f"{avg_conf:.2f}")

    st.divider()

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.subheader("Review status")
        if reviews:
            st.bar_chart(_count_chart(reviews, "status", "count"))
        else:
            st.info("No review queue entries yet.")

    with chart_cols[1]:
        st.subheader("Risk level distribution")
        st.bar_chart(_count_chart(tickets, "risk_level", "count"))

    st.subheader("Tickets by category (intent)")
    st.bar_chart(_count_chart(tickets, "intent", "count"))

    st.divider()
    st.subheader("Recent tickets")
    st.dataframe(
        pd.DataFrame(tickets),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Recent audit log entries"):
        st.dataframe(
            pd.DataFrame(logs),
            use_container_width=True,
            hide_index=True,
        )
