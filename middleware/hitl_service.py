"""
BuildWise human-in-the-loop (HITL) service (scaffold).

Member 2 backend — placeholder for review-queue logic: deciding when
responses need human approval and writing entries to
``data/review_queue.json``.
"""

from __future__ import annotations

from typing import Any, Dict, List


def should_send_to_review(confidence: float, risk_level: str, risk_flags: List[str]) -> bool:
    """
    Return True if the response should enter the human review queue.

    Placeholder — always returns ``False`` until HITL rules are wired.
    """
    _ = (confidence, risk_level, risk_flags)
    return False


def append_review_item(item: Dict[str, Any]) -> bool:
    """
    Append a pending review item to ``data/review_queue.json``.

    Placeholder — not implemented yet.
    """
    _ = item
    return False
