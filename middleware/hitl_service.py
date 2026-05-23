"""
BuildWise human-in-the-loop (HITL) review queue service.

Persists review items to ``data/review_queue.json`` for cases that need
human approval before a response is sent to the customer.

Typical flow::

    risk = check_risk(agent_response, query)
    if risk["review_required"]:
        add_to_queue(query, agent_response, risk)

Review item schema::

    {
        "review_id": "REV-...",
        "timestamp": "...",
        "query": "...",
        "intent": "...",
        "original_response": "...",
        "edited_response": null,
        "final_response": null,
        "confidence": 0.0,
        "risk_flags": [...],
        "risk_level": "low|medium|high",
        "status": "pending|approved|rejected|edited",
        "reviewer": null,
        "reviewed_at": null,
        "rejection_reason": null,
        "sources": [...]
    }
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVIEW_QUEUE_PATH = PROJECT_ROOT / "data" / "review_queue.json"

VALID_STATUSES = frozenset({"pending", "approved", "rejected", "edited"})


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_data_dir() -> None:
    """Create ``data/`` if it does not exist."""
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _new_review_id() -> str:
    """Generate a unique review identifier."""
    return f"REV-{uuid.uuid4().hex[:8].upper()}"


def load_review_queue() -> List[Dict[str, Any]]:
    """
    Load all review items from ``data/review_queue.json``.

    Returns an empty list when the file is missing, empty, or corrupted.
    """
    _ensure_data_dir()

    if not REVIEW_QUEUE_PATH.is_file() or REVIEW_QUEUE_PATH.stat().st_size == 0:
        return []

    try:
        raw = REVIEW_QUEUE_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        logger.warning("review_queue.json root is not a list; resetting to []")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load review queue (%s); using []", exc)
        return []


def save_review_queue(queue: List[Dict[str, Any]]) -> bool:
    """
    Persist the review queue to disk.

    Args:
        queue: List of review item dicts.

    Returns:
        True on success, False on write failure.
    """
    _ensure_data_dir()
    try:
        REVIEW_QUEUE_PATH.write_text(
            json.dumps(queue, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.error("Failed to save review queue: %s", exc)
        return False


def _find_review_index(queue: List[Dict[str, Any]], review_id: str) -> int:
    """Return index of *review_id* in *queue*, or ``-1`` if not found."""
    for index, item in enumerate(queue):
        if item.get("review_id") == review_id:
            return index
    return -1


def _success_result(
    message: str,
    *,
    review_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standard success response dict."""
    result: Dict[str, Any] = {"success": True, "message": message}
    if review_id is not None:
        result["review_id"] = review_id
    if data is not None:
        result["data"] = data
    return result


def _error_result(message: str, *, review_id: Optional[str] = None) -> Dict[str, Any]:
    """Build a standard error response dict."""
    result: Dict[str, Any] = {"success": False, "message": message}
    if review_id is not None:
        result["review_id"] = review_id
    return result


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


def add_to_queue(
    query: str,
    agent_response: Dict[str, Any],
    risk_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Append a pending review item built from agent output and risk evaluation.

    Args:
        query: Original user message.
        agent_response: Member 1 agent dict.
        risk_result: Output from ``check_risk()``.

    Returns:
        Dict with ``success``, ``message``, ``review_id``, and ``data`` (item).
    """
    review_id = _new_review_id()
    try:
        confidence = float(agent_response.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    item: Dict[str, Any] = {
        "review_id": review_id,
        "timestamp": _utc_now_iso(),
        "query": query or "",
        "intent": str(agent_response.get("intent", "") or ""),
        "original_response": str(
            agent_response.get("response")
            or agent_response.get("final_response")
            or ""
        ),
        "edited_response": None,
        "final_response": None,
        "confidence": round(confidence, 2),
        "risk_flags": list(risk_result.get("risk_flags") or []),
        "risk_level": str(risk_result.get("risk_level", "low") or "low").lower(),
        "status": "pending",
        "reviewer": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "sources": list(agent_response.get("sources") or []),
    }

    queue = load_review_queue()
    queue.append(item)

    if not save_review_queue(queue):
        return _error_result("Failed to save review item to queue.")

    return _success_result(
        "Review item added to queue.",
        review_id=review_id,
        data=item,
    )


def get_pending_reviews() -> List[Dict[str, Any]]:
    """
    Return review items with ``status == "pending"``.

    Order matches append order in the JSON file.
    """
    return [item for item in load_review_queue() if item.get("status") == "pending"]


def approve_response(
    review_id: str,
    reviewer: str = "human_reviewer",
) -> Dict[str, Any]:
    """
    Approve a pending review.

    Sets ``status`` to ``approved`` and ``final_response`` to ``edited_response``
    when present, otherwise ``original_response``.
    """
    queue = load_review_queue()
    index = _find_review_index(queue, review_id)
    if index < 0:
        return _error_result(f"Review ID not found: {review_id}", review_id=review_id)

    item = queue[index]
    if item.get("status") != "pending":
        return _error_result(
            f"Review {review_id} is not pending (status={item.get('status')}).",
            review_id=review_id,
        )

    final_text = item.get("edited_response") or item.get("original_response") or ""
    item["status"] = "approved"
    item["final_response"] = final_text
    item["reviewer"] = reviewer
    item["reviewed_at"] = _utc_now_iso()
    queue[index] = item

    if not save_review_queue(queue):
        return _error_result("Failed to save queue after approval.", review_id=review_id)

    return _success_result(
        "Review approved.",
        review_id=review_id,
        data=item,
    )


def reject_response(
    review_id: str,
    reviewer: str = "human_reviewer",
    reason: str = "",
) -> Dict[str, Any]:
    """
    Reject a pending review and store an optional ``rejection_reason``.
    """
    queue = load_review_queue()
    index = _find_review_index(queue, review_id)
    if index < 0:
        return _error_result(f"Review ID not found: {review_id}", review_id=review_id)

    item = queue[index]
    if item.get("status") != "pending":
        return _error_result(
            f"Review {review_id} is not pending (status={item.get('status')}).",
            review_id=review_id,
        )

    item["status"] = "rejected"
    item["final_response"] = None
    item["reviewer"] = reviewer
    item["reviewed_at"] = _utc_now_iso()
    item["rejection_reason"] = reason or None
    queue[index] = item

    if not save_review_queue(queue):
        return _error_result("Failed to save queue after rejection.", review_id=review_id)

    return _success_result(
        "Review rejected.",
        review_id=review_id,
        data=item,
    )


def edit_response(
    review_id: str,
    edited_response: str,
    reviewer: str = "human_reviewer",
) -> Dict[str, Any]:
    """
    Edit a pending review response before approval.

    Sets ``status`` to ``edited``, stores ``edited_response``, and sets
    ``final_response`` to the edited text.
    """
    queue = load_review_queue()
    index = _find_review_index(queue, review_id)
    if index < 0:
        return _error_result(f"Review ID not found: {review_id}", review_id=review_id)

    item = queue[index]
    if item.get("status") != "pending":
        return _error_result(
            f"Review {review_id} is not pending (status={item.get('status')}).",
            review_id=review_id,
        )

    if not edited_response or not edited_response.strip():
        return _error_result("Edited response cannot be empty.", review_id=review_id)

    item["status"] = "edited"
    item["edited_response"] = edited_response.strip()
    item["final_response"] = edited_response.strip()
    item["reviewer"] = reviewer
    item["reviewed_at"] = _utc_now_iso()
    queue[index] = item

    if not save_review_queue(queue):
        return _error_result("Failed to save queue after edit.", review_id=review_id)

    return _success_result(
        "Review response edited.",
        review_id=review_id,
        data=item,
    )


# ---------------------------------------------------------------------------
# Legacy / helper API (preserved from scaffold)
# ---------------------------------------------------------------------------


def should_send_to_review(
    confidence: float,
    risk_level: str,
    risk_flags: List[str],
) -> bool:
    """
    Return True if the response should enter the human review queue.

    Delegates to ``risk_rules.check_risk`` for consistent review logic.
    """
    from middleware.risk_rules import check_risk

    result = check_risk(
        {
            "intent": "",
            "confidence": confidence,
            "risk_flags": risk_flags,
        },
        query="",
    )
    level = (risk_level or "").lower()
    return bool(result["review_required"]) or level in ("medium", "high")


def append_review_item(item: Dict[str, Any]) -> bool:
    """
    Append a pre-built review item dict to the queue.

    Returns False if the item lacks ``review_id`` or the ID already exists.
    """
    review_id = item.get("review_id")
    if not review_id:
        logger.warning("append_review_item: missing review_id")
        return False

    queue = load_review_queue()
    if any(existing.get("review_id") == review_id for existing in queue):
        logger.warning("append_review_item: duplicate review_id %s", review_id)
        return False

    queue.append(item)
    return save_review_queue(queue)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import json as _json
    import sys

    # Allow running as: python middleware/hitl_service.py
    sys.path.insert(0, str(PROJECT_ROOT))

    from middleware.risk_rules import check_risk

    print("BuildWise HITL service — test run\n")

    sample_query = "Why is Tower B delayed?"
    sample_agent = {
        "intent": "construction_status",
        "response": (
            "Tower B is delayed due to material delivery issues. "
            "Current completion is 72%."
        ),
        "confidence": 0.72,
        "risk_flags": ["construction_delay", "high_risk"],
        "sources": ["construction_status.csv"],
    }
    sample_risk = check_risk(sample_agent, sample_query)

    # Start from a clean queue for deterministic demo output
    save_review_queue([])

    print("1. Adding sample review to queue...")
    add_result = add_to_queue(sample_query, sample_agent, sample_risk)
    print(f"   success   : {add_result['success']}")
    print(f"   review_id : {add_result.get('review_id')}")
    print(f"   message   : {add_result['message']}")

    print("\n2. Pending reviews:")
    pending = get_pending_reviews()
    print(f"   count: {len(pending)}")
    for item in pending:
        print(
            f"   - {item['review_id']} | {item['query'][:40]} | "
            f"risk={item['risk_level']} | status={item['status']}"
        )

    review_id = add_result.get("review_id", "")
    print(f"\n3. Approving review {review_id}...")
    approve_result = approve_response(review_id)
    print(f"   success : {approve_result['success']}")
    print(f"   message : {approve_result['message']}")
    if approve_result.get("data"):
        print(f"   final   : {approve_result['data'].get('final_response', '')[:80]}...")

    print("\n4. Updated queue:")
    updated = load_review_queue()
    print(_json.dumps(updated, indent=2))

    assert add_result["success"] is True
    assert len(pending) == 1
    assert approve_result["success"] is True
    assert get_pending_reviews() == []
    assert updated[0]["status"] == "approved"
    assert updated[0]["final_response"] is not None

    print("\nAll HITL service checks: PASS")
