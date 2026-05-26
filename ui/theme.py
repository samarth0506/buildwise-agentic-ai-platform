"""
BuildWise enterprise UI theme — global CSS and reusable visual components.

Streamlit-only styling layer. Does not touch backend or middleware logic.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

# Optional Plotly for polished charts (falls back to st.bar_chart)
try:
    import plotly.express as px
    import plotly.graph_objects as go

    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

COLORS = {
    "accent": "#3b82f6",
    "accent_soft": "rgba(59, 130, 246, 0.15)",
    "success": "#10b981",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#06b6d4",
    "purple": "#8b5cf6",
    "bg_card": "#121826",
    "border": "rgba(148, 163, 184, 0.18)",
    "text_muted": "#94a3b8",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ASSETS = PROJECT_ROOT / "assets" / "dashboard"

DASHBOARD_BANNERS: dict[str, Path] = {
    "activity": DASHBOARD_ASSETS / "recent_activity.svg",
    "escalations": DASHBOARD_ASSETS / "recent_escalations.svg",
    "risk": DASHBOARD_ASSETS / "top_risk.svg",
}

NAV_ITEMS: list[tuple[str, str, str]] = [
    ("Chatbot", "💬", "AI assistant & agent routing"),
    ("Human Review Queue", "📋", "HITL moderation dashboard"),
    ("Dashboard", "📊", "Operations analytics"),
]

CHIP_VARIANTS = {
    "agent": ("#3b82f6", "rgba(59,130,246,0.18)"),
    "confidence": ("#8b5cf6", "rgba(139,92,246,0.18)"),
    "risk_low": ("#10b981", "rgba(16,185,129,0.18)"),
    "risk_medium": ("#f59e0b", "rgba(245,158,11,0.18)"),
    "risk_high": ("#ef4444", "rgba(239,68,68,0.18)"),
    "hitl": ("#f59e0b", "rgba(245,158,11,0.22)"),
    "approved": ("#10b981", "rgba(16,185,129,0.18)"),
    "pending": ("#f59e0b", "rgba(245,158,11,0.18)"),
    "rejected": ("#ef4444", "rgba(239,68,68,0.18)"),
    "edited": ("#3b82f6", "rgba(59,130,246,0.18)"),
    "default": ("#94a3b8", "rgba(148,163,184,0.15)"),
}


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------


def inject_global_css() -> None:
    """Inject enterprise dark-theme styles (safe to call once per rerun)."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bw-accent: #3b82f6;
            --bw-accent-2: #8b5cf6;
            --bw-success: #10b981;
            --bw-warning: #f59e0b;
            --bw-danger: #ef4444;
            --bw-card: #121826;
            --bw-card-hover: #1a2235;
            --bw-border: rgba(148, 163, 184, 0.18);
            --bw-text-muted: #94a3b8;
        }

        .stApp {
            background: linear-gradient(165deg, #070b14 0%, #0b1120 45%, #0f172a 100%);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
        }

        h1, h2, h3, h4 { letter-spacing: -0.02em; }

        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0a0f1a 0%, #0f172a 100%);
            border-right: 1px solid var(--bw-border);
        }

        div[data-testid="stSidebar"] .stMarkdown p,
        div[data-testid="stSidebar"] .stMarkdown small {
            color: var(--bw-text-muted);
        }

        /* Sidebar nav buttons */
        div[data-testid="stSidebar"] button[kind="secondary"] {
            width: 100%;
            border: 1px solid var(--bw-border);
            border-radius: 10px;
            background: rgba(18, 24, 38, 0.6);
            color: #e2e8f0;
            padding: 0.55rem 0.75rem;
            margin-bottom: 0.35rem;
            transition: all 0.2s ease;
            text-align: left;
        }

        div[data-testid="stSidebar"] button[kind="secondary"]:hover {
            border-color: var(--bw-accent);
            background: var(--bw-card-hover);
            transform: translateX(2px);
        }

        div[data-testid="stSidebar"] button.bw-nav-active {
            border-color: var(--bw-accent) !important;
            background: linear-gradient(90deg, rgba(59,130,246,0.22), rgba(139,92,246,0.08)) !important;
            box-shadow: 0 0 0 1px rgba(59,130,246,0.35);
        }

        /* Primary buttons */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #3b82f6, #6366f1);
            border: none;
            border-radius: 8px;
            font-weight: 600;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(59, 130, 246, 0.35);
        }

        /* Metrics */
        div[data-testid="stMetric"] {
            background: var(--bw-card);
            border: 1px solid var(--bw-border);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25);
            transition: border-color 0.2s ease, transform 0.2s ease;
        }

        div[data-testid="stMetric"]:hover {
            border-color: rgba(59, 130, 246, 0.4);
            transform: translateY(-2px);
        }

        div[data-testid="stMetric"] label {
            color: var(--bw-text-muted) !important;
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        /* Expanders */
        .streamlit-expanderHeader {
            background: var(--bw-card);
            border-radius: 10px;
            border: 1px solid var(--bw-border);
        }

        /* Dataframes */
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--bw-border);
            border-radius: 12px;
            overflow: hidden;
        }

        /* Chat input */
        div[data-testid="stChatInput"] textarea {
            border-radius: 12px !important;
            border: 1px solid var(--bw-border) !important;
            background: var(--bw-card) !important;
        }

        /* Progress bars */
        .stProgress > div > div {
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
            border-radius: 6px;
        }

        /* Hide Streamlit chrome */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# HTML building blocks
# ---------------------------------------------------------------------------


def _chip_html(label: str, fg: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;padding:0.28rem 0.65rem;margin:0.15rem 0.25rem 0.15rem 0;'
        f"border-radius:999px;font-size:0.72rem;font-weight:600;color:{fg};"
        f'background:{bg};border:1px solid {fg}33;">{label}</span>'
    )


def chip_row(chips: list[tuple[str, str]]) -> None:
    """Render a row of colored status chips. chips = [(label, variant), ...]."""
    html_parts = ['<div style="margin:0.5rem 0 0.75rem 0;display:flex;flex-wrap:wrap;gap:0.1rem;">']
    for label, variant in chips:
        fg, bg = CHIP_VARIANTS.get(variant, CHIP_VARIANTS["default"])
        html_parts.append(_chip_html(label, fg, bg))
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def page_header(title: str, subtitle: str, badge: str = "Live") -> None:
    """Hero header for each main page."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, rgba(59,130,246,0.12) 0%, rgba(139,92,246,0.08) 100%);
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 1.35rem 1.5rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 32px rgba(0,0,0,0.35);
        ">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:0.75rem;">
                <div>
                    <h1 style="margin:0;font-size:1.65rem;font-weight:700;color:#f1f5f9;">{title}</h1>
                    <p style="margin:0.35rem 0 0;color:{COLORS['text_muted']};font-size:0.92rem;">{subtitle}</p>
                </div>
                <span style="
                    padding:0.35rem 0.85rem;border-radius:999px;font-size:0.75rem;font-weight:600;
                    color:{COLORS['success']};background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.35);
                ">● {badge}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str | int, icon: str = "📌", accent: str = "#3b82f6") -> None:
    """Styled KPI metric card."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, #121826 0%, #161f33 100%);
            border: 1px solid {COLORS['border']};
            border-left: 3px solid {accent};
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 6px 24px rgba(0,0,0,0.28);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        ">
            <div style="font-size:1.35rem;margin-bottom:0.35rem;">{icon}</div>
            <div style="color:{COLORS['text_muted']};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;">{label}</div>
            <div style="color:#f8fafc;font-size:1.65rem;font-weight:700;margin-top:0.25rem;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str = "") -> None:
    """Section heading with optional subtitle."""
    sub = f'<p style="margin:0.2rem 0 0.75rem;color:{COLORS["text_muted"]};font-size:0.85rem;">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<h3 style="margin:1.25rem 0 0.35rem;color:#e2e8f0;font-size:1.05rem;font-weight:600;">{title}</h3>{sub}',
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, message: str) -> None:
    """Friendly empty-state panel."""
    st.markdown(
        f"""
        <div style="
            text-align:center;padding:2.5rem 1.5rem;
            background:{COLORS['bg_card']};border:1px dashed {COLORS['border']};
            border-radius:16px;margin:1rem 0;
        ">
            <div style="font-size:2.5rem;margin-bottom:0.5rem;">{icon}</div>
            <div style="color:#e2e8f0;font-weight:600;font-size:1.1rem;margin-bottom:0.35rem;">{title}</div>
            <div style="color:{COLORS['text_muted']};font-size:0.9rem;max-width:420px;margin:0 auto;">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_banner(message: str, variant: str = "warning") -> None:
    """Colored alert strip (warning | danger | success | info)."""
    palette = {
        "warning": ("#f59e0b", "rgba(245,158,11,0.12)"),
        "danger": ("#ef4444", "rgba(239,68,68,0.12)"),
        "success": ("#10b981", "rgba(16,185,129,0.12)"),
        "info": ("#3b82f6", "rgba(59,130,246,0.12)"),
    }
    fg, bg = palette.get(variant, palette["info"])
    st.markdown(
        f"""
        <div style="
            padding:0.85rem 1rem;border-radius:10px;margin:0.75rem 0;
            border:1px solid {fg}44;background:{bg};color:{fg};font-weight:500;font-size:0.9rem;
        ">{message}</div>
        """,
        unsafe_allow_html=True,
    )


def assistant_response_block(content: str) -> None:
    """Styled assistant card that still renders Streamlit Markdown."""
    with st.container(border=True):
        st.markdown(content or "_No response._")


def user_bubble(content: str) -> None:
    """Right-aligned user message bubble."""
    safe = html.escape(content or "")
    st.markdown(
        f"""
        <div style="display:flex;justify-content:flex-end;margin:0.75rem 0;">
            <div style="
                max-width:78%;background:linear-gradient(135deg,#3b82f6,#6366f1);
                color:#fff;padding:0.85rem 1.1rem;border-radius:16px 16px 4px 16px;
                box-shadow:0 6px 20px rgba(59,130,246,0.35);font-size:0.95rem;line-height:1.5;
            ">{safe}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def confidence_meter(score: float, label: str = "Confidence") -> None:
    """Visual confidence bar with percentage label."""
    pct = min(max(score, 0.0), 1.0)
    color = COLORS["success"] if pct >= 0.75 else COLORS["warning"] if pct >= 0.6 else COLORS["danger"]
    st.markdown(
        f"""
        <div style="margin:0.5rem 0 1rem;">
            <div style="display:flex;justify-content:space-between;margin-bottom:0.35rem;">
                <span style="color:{COLORS['text_muted']};font-size:0.8rem;font-weight:500;">{label}</span>
                <span style="color:{color};font-weight:700;font-size:0.85rem;">{pct:.0%}</span>
            </div>
            <div style="background:rgba(148,163,184,0.15);border-radius:8px;height:8px;overflow:hidden;">
                <div style="width:{pct*100}%;height:100%;background:linear-gradient(90deg,{color},{color}cc);border-radius:8px;transition:width 0.4s ease;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(pct)


def workflow_timeline(steps: list[tuple[str, bool]]) -> None:
    """
    Vertical workflow with checkmarks.

    steps: list of (label, completed).
    """
    rows = []
    for label, done in steps:
        icon = "✔" if done else "○"
        color = COLORS["success"] if done else COLORS["text_muted"]
        rows.append(
            f'<div style="display:flex;align-items:center;gap:0.65rem;padding:0.4rem 0;">'
            f'<span style="color:{color};font-weight:700;font-size:0.95rem;">{icon}</span>'
            f'<span style="color:{"#e2e8f0" if done else COLORS["text_muted"]};font-size:0.88rem;">{label}</span></div>'
        )
    st.markdown(
        f"""
        <div style="
            background:{COLORS['bg_card']};border:1px solid {COLORS['border']};
            border-radius:12px;padding:0.75rem 1rem;margin:0.5rem 0;
        ">{"".join(rows)}</div>
        """,
        unsafe_allow_html=True,
    )


def risk_variant(level: str) -> str:
    key = (level or "low").lower()
    if key == "high":
        return "risk_high"
    if key == "medium":
        return "risk_medium"
    return "risk_low"


def render_plotly_bar(
    df: pd.DataFrame,
    title: str,
    color: str = "#3b82f6",
) -> None:
    """Plotly bar chart with dark theme, or Streamlit fallback."""
    if df.empty or df.iloc[:, 0].sum() == 0 if len(df.columns) else True:
        st.caption("No data to chart.")
        return

    if HAS_PLOTLY:
        chart_df = df.reset_index()
        x_col = chart_df.columns[0]
        y_col = chart_df.columns[1]
        fig = px.bar(
            chart_df,
            x=x_col,
            y=y_col,
            title=title,
            color_discrete_sequence=[color],
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
            height=280,
            font=dict(family="Inter, sans-serif", size=12),
            title_font_size=14,
        )
        fig.update_traces(marker_line_width=0, opacity=0.9)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(df)


def render_plotly_pie(labels: list[str], values: list[int], title: str) -> None:
    """Pie/donut chart for distributions."""
    if not values or sum(values) == 0:
        st.caption("No data to chart.")
        return

    if HAS_PLOTLY:
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.55,
                    marker=dict(colors=["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]),
                )
            ]
        )
        fig.update_layout(
            template="plotly_dark",
            title=title,
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=40, b=10),
            height=280,
            showlegend=True,
            font=dict(family="Inter, sans-serif"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.bar_chart(pd.DataFrame({"count": values}, index=labels))


def operations_panel(
    title: str,
    banner_key: str,
    render_body: Callable[[], None],
) -> None:
    """
    Dashboard live-ops card with a header banner image and scrollable body.

    Uses native Streamlit containers so images and list items render correctly.
    """
    banner_path = DASHBOARD_BANNERS.get(banner_key)

    with st.container(border=True):
        if banner_path and banner_path.is_file():
            st.image(str(banner_path), use_container_width=True)
        else:
            st.markdown(
                f"""
                <div style="
                    height:100px;border-radius:12px;
                    background:linear-gradient(135deg,#1e293b,#334155);
                    display:flex;align-items:center;justify-content:center;
                    color:#94a3b8;font-size:0.9rem;margin-bottom:0.5rem;
                ">Banner: {html.escape(title)}</div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<p style="color:#e2e8f0;font-weight:600;font-size:0.95rem;margin:0.5rem 0 0.75rem;">{html.escape(title)}</p>',
            unsafe_allow_html=True,
        )
        render_body()


# Category thumbnails for dashboard activity cards (emoji + gradient tile)
INTENT_VISUALS: dict[str, tuple[str, str]] = {
    "construction_status": ("🏗️", "linear-gradient(135deg,#3b82f6,#1d4ed8)"),
    "documentation_support": ("📄", "linear-gradient(135deg,#8b5cf6,#6d28d9)"),
    "maintenance_issue": ("🔧", "linear-gradient(135deg,#06b6d4,#0891b2)"),
    "property_inquiry": ("🏠", "linear-gradient(135deg,#10b981,#059669)"),
    "escalation": ("🚨", "linear-gradient(135deg,#ef4444,#b91c1c)"),
    "general_inquiry": ("💬", "linear-gradient(135deg,#64748b,#475569)"),
}

ISSUE_VISUALS: dict[str, tuple[str, str]] = {
    "escalation": ("🚨", "linear-gradient(135deg,#ef4444,#b91c1c)"),
    "payment_dispute": ("💳", "linear-gradient(135deg,#f59e0b,#d97706)"),
    "legal_issue": ("⚖️", "linear-gradient(135deg,#a855f7,#7c3aed)"),
    "safety_issue": ("🛡️", "linear-gradient(135deg,#ef4444,#991b1b)"),
    "maintenance_issue": ("🚿", "linear-gradient(135deg,#06b6d4,#0e7490)"),
    "construction_concern": ("🏗️", "linear-gradient(135deg,#3b82f6,#1e40af)"),
}

RISK_VISUALS: dict[str, tuple[str, str]] = {
    "high": ("🔴", "linear-gradient(135deg,#ef4444,#991b1b)"),
    "medium": ("🟠", "linear-gradient(135deg,#f59e0b,#b45309)"),
    "low": ("🟢", "linear-gradient(135deg,#10b981,#047857)"),
}


def visual_for_intent(intent: str, query: str = "") -> tuple[str, str]:
    """Return (emoji, gradient) for an audit-log / activity row."""
    key = (intent or "").lower().strip()
    if key in INTENT_VISUALS:
        return INTENT_VISUALS[key]
    text = (query or "").lower()
    if any(w in text for w in ("tower", "construction", "delay")):
        return INTENT_VISUALS["construction_status"]
    if any(w in text for w in ("kyc", "document", "registration")):
        return INTENT_VISUALS["documentation_support"]
    if any(w in text for w in ("leak", "plumbing", "maintenance")):
        return INTENT_VISUALS["maintenance_issue"]
    if any(w in text for w in ("2bhk", "property", "apartment")):
        return INTENT_VISUALS["property_inquiry"]
    if any(w in text for w in ("angry", "dispute", "refund", "legal")):
        return INTENT_VISUALS["escalation"]
    return INTENT_VISUALS["general_inquiry"]


def visual_for_issue(issue_type: str, query: str = "") -> tuple[str, str]:
    """Return (emoji, gradient) for an escalation ticket row."""
    key = (issue_type or "").lower().strip()
    if key in ISSUE_VISUALS:
        return ISSUE_VISUALS[key]
    text = (query or "").lower()
    if "payment" in text or "refund" in text or "dispute" in text:
        return ISSUE_VISUALS["payment_dispute"]
    if "legal" in text:
        return ISSUE_VISUALS["legal_issue"]
    if "safety" in text:
        return ISSUE_VISUALS["safety_issue"]
    return ISSUE_VISUALS["escalation"]


def visual_for_risk(risk_level: str, intent: str = "") -> tuple[str, str]:
    """Return (emoji, gradient) for a high-risk review row."""
    level = (risk_level or "high").lower().strip()
    emoji, gradient = RISK_VISUALS.get(level, RISK_VISUALS["high"])
    intent_key = (intent or "").lower().strip()
    if intent_key in INTENT_VISUALS:
        return INTENT_VISUALS[intent_key]
    return emoji, gradient


def activity_feed_item(
    timestamp: str,
    headline: str,
    detail: str,
    badge: str,
    badge_variant: str = "default",
    *,
    visual_emoji: str = "📌",
    visual_gradient: str = "linear-gradient(135deg,#3b82f6,#6366f1)",
) -> None:
    """Single row in an activity feed with a category thumbnail."""
    fg, bg = CHIP_VARIANTS.get(badge_variant, CHIP_VARIANTS["default"])
    safe_headline = html.escape(headline)
    safe_detail = html.escape(detail)
    safe_ts = html.escape(timestamp)
    safe_badge = html.escape(badge)

    st.markdown(
        f"""
        <div style="
            display:flex;align-items:flex-start;gap:0.85rem;
            padding:0.85rem 0;border-bottom:1px solid {COLORS['border']};
        ">
            <div style="
                width:52px;height:52px;min-width:52px;border-radius:14px;
                background:{visual_gradient};
                display:flex;align-items:center;justify-content:center;
                font-size:1.55rem;box-shadow:0 6px 18px rgba(0,0,0,0.35);
            ">{visual_emoji}</div>
            <div style="flex:1;min-width:0;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem;">
                    <div style="color:#e2e8f0;font-weight:600;font-size:0.88rem;">{safe_headline}</div>
                    {_chip_html(safe_badge, fg, bg)}
                </div>
                <div style="color:{COLORS['text_muted']};font-size:0.78rem;margin-top:0.35rem;line-height:1.4;">{safe_detail}</div>
                <div style="color:{COLORS['text_muted']};font-size:0.72rem;margin-top:0.3rem;">🕐 {safe_ts}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    """BuildWise logo block in sidebar."""
    st.markdown(
        """
        <div style="text-align:center;padding:0.5rem 0 1rem;">
            <div style="
                width:52px;height:52px;margin:0 auto 0.65rem;
                background:linear-gradient(135deg,#3b82f6,#8b5cf6);
                border-radius:14px;display:flex;align-items:center;justify-content:center;
                font-size:1.6rem;box-shadow:0 8px 24px rgba(59,130,246,0.4);
            ">🏗️</div>
            <div style="color:#f1f5f9;font-weight:700;font-size:1.15rem;letter-spacing:-0.02em;">BuildWise</div>
            <div style="color:#64748b;font-size:0.72rem;margin-top:0.15rem;">Agentic AI Platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_status_footer() -> None:
    """App status strip at bottom of sidebar."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div style="
            margin-top:1.5rem;padding:0.85rem;
            background:rgba(18,24,38,0.8);border:1px solid {COLORS['border']};
            border-radius:10px;font-size:0.75rem;color:{COLORS['text_muted']};
        ">
            <div style="color:#10b981;font-weight:600;margin-bottom:0.35rem;">● Systems operational</div>
            <div>Middleware connected</div>
            <div style="margin-top:0.25rem;">Session: {now}</div>
            <div style="margin-top:0.5rem;color:#475569;">v0.2 · Enterprise UI</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_nav() -> str:
    """
    Card-style sidebar navigation. Returns selected page name.

    Uses session_state.nav_page.
    """
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = NAV_ITEMS[0][0]

    sidebar_brand()
    st.markdown(
        f'<p style="color:{COLORS["text_muted"]};font-size:0.72rem;text-transform:uppercase;letter-spacing:0.1em;margin:0.5rem 0 0.75rem;">Navigation</p>',
        unsafe_allow_html=True,
    )

    for page_name, icon, desc in NAV_ITEMS:
        is_active = st.session_state.nav_page == page_name
        label = f"{icon}  {page_name}"
        if st.button(
            label,
            key=f"nav_{page_name}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.nav_page = page_name
            st.rerun()

    st.markdown(
        f'<hr style="border:none;border-top:1px solid {COLORS["border"]};margin:1rem 0;" />',
        unsafe_allow_html=True,
    )
    sidebar_status_footer()

    return st.session_state.nav_page
