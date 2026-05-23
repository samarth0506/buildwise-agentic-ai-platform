"""
BuildWise Agentic AI — Streamlit entrypoint.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st

from ui import show_chat, show_dashboard, show_review_queue

PAGES = {
    "Chatbot": show_chat,
    "Human Review Queue": show_review_queue,
    "Dashboard": show_dashboard,
}


def _ensure_data_folder() -> None:
    """Create data/ on first launch so child pages can safely write JSON."""
    os.makedirs("data", exist_ok=True)


def _configure_page() -> None:
    st.set_page_config(
        page_title="BuildWise Agentic AI",
        page_icon=":building_construction:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _render_sidebar() -> str:
    with st.sidebar:
        st.title("BuildWise")
        st.caption("Agentic AI platform for real estate operations")
        st.divider()
        choice = st.radio(
            "Navigation",
            options=list(PAGES.keys()),
            index=0,
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("v0.1 — capstone build")
    return choice


def main() -> None:
    _configure_page()
    _ensure_data_folder()
    choice = _render_sidebar()
    page_fn = PAGES.get(choice, show_chat)
    page_fn()


if __name__ == "__main__":
    main()
