"""
BuildWise operations dashboard — enterprise analytics UI.

Reads live data from middleware JSON stores. Backend logic unchanged.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

from middleware.audit_logger import get_audit_logs, get_audit_summary
from middleware.hitl_service import load_review_queue
from middleware.ticket_service import get_all_tickets
from ui.theme import (
    COLORS,
    activity_feed_item,
    empty_state,
    kpi_card,
    operations_panel,
    page_header,
    render_plotly_bar,
    render_plotly_pie,
    section_title,
    visual_for_intent,
    visual_for_issue,
    visual_for_risk,
)


# ---------------------------------------------------------------------------
# Data helpers (unchanged logic)
# ---------------------------------------------------------------------------


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _count_df(items: list[dict[str, Any]], key: str, label: str = "count") -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    counts = Counter(
        str(item.get(key, "unknown")).strip().lower() or "unknown" for item in items
    )
    return pd.DataFrame({label: list(counts.values())}, index=list(counts.keys()))


def _audit_action_label(entry: dict[str, Any]) -> str:
    if entry.get("event_type"):
        return str(entry["event_type"])
    if entry.get("review_required"):
        return "sent_to_review"
    return "query_processed"


def _audit_table_rows(logs: list[dict[str, Any]]) -> list[dict[str, str]]:
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
# Page
# ---------------------------------------------------------------------------


def show_dashboard() -> None:
    """Render the BuildWise operations dashboard."""
    page_header(
        "Operations Dashboard",
        "Real-time analytics across tickets, human review queue, audit logs, and risk signals.",
        badge="Analytics",
    )

    tickets = get_all_tickets()
    reviews = load_review_queue()
    logs = get_audit_logs()
    summary = get_audit_summary()

    pending_reviews = sum(1 for r in reviews if r.get("status") == "pending")
    approved_reviews = sum(1 for r in reviews if r.get("status") == "approved")
    rejected_reviews = sum(1 for r in reviews if r.get("status") == "rejected")

    escalations = [
        t
        for t in tickets
        if (t.get("intent") or "").lower() == "escalation"
        or (t.get("issue_type") or "").lower() == "escalation"
    ]

    avg_confidence = summary.get("average_confidence", 0.0)
    if not avg_confidence and logs:
        avg_confidence = _safe_mean(
            [float(e.get("confidence", 0) or 0) for e in logs]
        )

    section_title("Key performance indicators")
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    with r1c1:
        kpi_card("Total tickets", len(tickets), "🎫", COLORS["accent"])
    with r1c2:
        kpi_card("Pending reviews", pending_reviews, "⏳", COLORS["warning"])
    with r1c3:
        kpi_card("Approved", approved_reviews, "✅", COLORS["success"])
    with r1c4:
        kpi_card("Rejected", rejected_reviews, "❌", COLORS["danger"])

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1:
        kpi_card("Escalations", len(escalations), "🚨", COLORS["danger"])
    with r2c2:
        kpi_card("Avg. confidence", f"{avg_confidence:.0%}" if avg_confidence <= 1 else f"{avg_confidence:.2f}", "📊", COLORS["purple"])
    with r2c3:
        kpi_card("Audit entries", len(logs), "📜", COLORS["info"])

    st.divider()

    # --- Charts ---
    section_title("Analytics", "Distribution and trend views from live JSON stores.")

    chart_row1 = st.columns(2)
    with chart_row1[0]:
        st.markdown(
            f'<div style="background:{COLORS["bg_card"]};border:1px solid {COLORS["border"]};border-radius:14px;padding:0.75rem 1rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("**Review status distribution**")
        review_status_df = _count_df(reviews, "status")
        if not review_status_df.empty:
            render_plotly_pie(
                list(review_status_df.index),
                list(review_status_df.iloc[:, 0]),
                "Review status",
            )
        else:
            st.caption("No review data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_row1[1]:
        st.markdown(
            f'<div style="background:{COLORS["bg_card"]};border:1px solid {COLORS["border"]};border-radius:14px;padding:0.75rem 1rem;">',
            unsafe_allow_html=True,
        )
        st.markdown("**Risk level distribution**")
        risk_source = logs if logs else reviews
        risk_df = _count_df(risk_source, "risk_level")
        if not risk_df.empty:
            render_plotly_bar(risk_df, "Risk levels", color=COLORS["warning"])
        else:
            st.caption("No risk data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    chart_row2 = st.columns(2)
    with chart_row2[0]:
        st.markdown("**Escalation breakdown**")
        if escalations:
            render_plotly_bar(
                _count_df(escalations, "issue_type"),
                "Escalations by issue type",
                color=COLORS["danger"],
            )
        else:
            st.info("No escalation tickets recorded yet.")

    with chart_row2[1]:
        st.markdown("**Ticket categories (intent)**")
        if tickets:
            render_plotly_bar(
                _count_df(tickets, "intent"),
                "Tickets by intent",
                color=COLORS["accent"],
            )
        else:
            st.info("No support tickets yet.")

    if logs:
        st.markdown("**Confidence analytics**")
        conf_values = [float(e.get("confidence", 0) or 0) for e in logs]
        conf_df = pd.DataFrame({"confidence": conf_values})
        st.line_chart(conf_df, height=220)

    st.divider()

    # --- Side panels ---
    section_title("Live operations", "Recent activity, escalations, and priority cases.")

    panel1, panel2, panel3 = st.columns(3)

    high_risk = sorted(
        [r for r in reviews if str(r.get("risk_level", "")).lower() == "high"],
        key=lambda r: float(r.get("confidence", 0)),
    )[:5]

    def _render_activity_feed() -> None:
        if logs:
            for entry in reversed(logs[-6:]):
                intent = str(entry.get("intent", "interaction"))
                query = str(entry.get("query", ""))
                emoji, gradient = visual_for_intent(intent, query)
                activity_feed_item(
                    str(entry.get("timestamp", "—"))[:19],
                    intent.replace("_", " ").title(),
                    query[:60] + ("…" if len(query) > 60 else ""),
                    str(entry.get("review_status", "logged")),
                    "pending" if entry.get("review_required") else "approved",
                    visual_emoji=emoji,
                    visual_gradient=gradient,
                )
        else:
            empty_state("📡", "No activity yet", "Use the Chatbot to generate audit log entries.")

    def _render_escalations_feed() -> None:
        if escalations:
            for ticket in reversed(escalations[-5:]):
                issue = str(ticket.get("issue_type", "escalation"))
                query = str(ticket.get("query", ""))
                emoji, gradient = visual_for_issue(issue, query)
                activity_feed_item(
                    str(ticket.get("timestamp", "—"))[:19],
                    issue.replace("_", " ").title(),
                    query[:55] + ("…" if len(query) > 55 else ""),
                    str(ticket.get("priority", "high")).upper(),
                    "risk_high",
                    visual_emoji=emoji,
                    visual_gradient=gradient,
                )
        else:
            empty_state("🚨", "No escalations", "Escalation tickets appear when disputes are raised.")

    def _render_risk_feed() -> None:
        if high_risk:
            for item in high_risk:
                intent = str(item.get("intent", ""))
                query = str(item.get("query", ""))
                emoji, gradient = visual_for_risk(
                    str(item.get("risk_level", "high")),
                    intent,
                )
                activity_feed_item(
                    _format_ts(item),
                    str(item.get("review_id", "—")),
                    query[:50] + ("…" if len(query) > 50 else ""),
                    str(item.get("status", "pending")),
                    "risk_high",
                    visual_emoji=emoji,
                    visual_gradient=gradient,
                )
        else:
            empty_state("🔴", "No high-risk cases", "High-risk reviews show up after flagged queries.")

    with panel1:
        operations_panel("📡 Recent activity", "activity", _render_activity_feed)

    with panel2:
        operations_panel("🚨 Recent escalations", "escalations", _render_escalations_feed)

    with panel3:
        operations_panel("🔴 Top risk cases", "risk", _render_risk_feed)

    st.divider()

    section_title("Recent audit log")
    if logs:
        st.dataframe(
            pd.DataFrame(_audit_table_rows(logs)),
            use_container_width=True,
            hide_index=True,
        )
    else:
        empty_state(
            "📜",
            "No audit logs",
            "Interactions are logged automatically when you use the Chatbot.",
        )

    with st.expander("📂 Full data tables"):
        t1, t2 = st.tabs(["Tickets", "Review queue"])
        with t1:
            if tickets:
                st.dataframe(pd.DataFrame(tickets), use_container_width=True, hide_index=True)
            else:
                st.caption("No tickets in data/tickets.json.")
        with t2:
            if reviews:
                st.dataframe(pd.DataFrame(reviews), use_container_width=True, hide_index=True)
            else:
                st.caption("No items in data/review_queue.json.")


def _format_ts(item: dict[str, Any]) -> str:
    return str(item.get("timestamp") or item.get("created_at") or "—")[:19]
