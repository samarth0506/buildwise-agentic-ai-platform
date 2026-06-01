"""
BuildWise Agentic AI — Streamlit entrypoint.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import logging
import os

import streamlit as st

# Show [LLM] / [ResponseAgent] lines in the Streamlit terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    force=True,
)

from ui import show_chat, show_dashboard, show_review_queue
from ui.theme import inject_global_css, render_sidebar_nav

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
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def main() -> None:
    _configure_page()
    inject_global_css()
    _ensure_data_folder()

    with st.sidebar:
        choice = render_sidebar_nav()

    page_fn = PAGES.get(choice, show_chat)
    page_fn()


if __name__ == "__main__":
    main()
