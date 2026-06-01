"""
BuildWise audit logger — append-only interaction logs for compliance and dashboards.

Persists records to ``data/audit_logs.json``. Designed so the router never crashes
if logging fails (errors are caught and returned as ``success: False``).

Typical flow::

    risk = check_risk(agent_response, query)
    log_interaction(
        query, intent, agent_response, risk,
        review_status="pending" if risk["review_required"] else "not_required",
        review_id=review_id,
    )
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
AUDIT_LOGS_PATH = PROJECT_ROOT / "data" / "audit_logs.json"

VALID_REVIEW_STATUSES = frozenset(
    {"not_required", "pending", "approved", "rejected", "edited"}
)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_data_dir() -> None:
    """Create ``data/`` if it does not exist."""
    AUDIT_LOGS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _new_log_id() -> str:
    """Generate a unique audit log identifier."""
    return f"LOG-{uuid.uuid4().hex[:8].upper()}"


def _success_result(
    message: str,
    *,
    log_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": True, "message": message}
    if log_id is not None:
        result["log_id"] = log_id
    if data is not None:
        result["data"] = data
    return result


def _error_result(message: str, *, log_id: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": False, "message": message}
    if log_id is not None:
        result["log_id"] = log_id
    return result


def load_audit_logs() -> List[Dict[str, Any]]:
    """
    Load all audit log entries from ``data/audit_logs.json``.

    Returns an empty list when the file is missing, empty, or corrupted.
    """
    _ensure_data_dir()

    if not AUDIT_LOGS_PATH.is_file() or AUDIT_LOGS_PATH.stat().st_size == 0:
        return []

    try:
        raw = AUDIT_LOGS_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [entry for entry in data if isinstance(entry, dict)]
        logger.warning("audit_logs.json root is not a list; using []")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load audit logs (%s); using []", exc)
        return []


def save_audit_logs(logs: List[Dict[str, Any]]) -> bool:
    """
    Persist audit logs to disk.

    Args:
        logs: List of audit log dicts.

    Returns:
        True on success, False on write failure.
    """
    _ensure_data_dir()
    try:
        AUDIT_LOGS_PATH.write_text(
            json.dumps(logs, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.error("Failed to save audit logs: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_interaction(
    query: str,
    intent: str,
    agent_response: Dict[str, Any],
    risk_result: Dict[str, Any],
    review_status: str,
    ticket_id: Optional[str] = None,
    review_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Append one interaction audit record.

    Args:
        query: User message.
        intent: Routed intent label.
        agent_response: Member 1 agent dict.
        risk_result: Output from ``check_risk()``.
        review_status: One of ``not_required``, ``pending``, ``approved``,
            ``rejected``, ``edited``.
        ticket_id: Optional support ticket reference.
        review_id: Optional HITL review reference.

    Returns:
        Dict with ``success``, ``message``, ``log_id``, and ``data`` (entry).
        Never raises — failures return ``success: False``.
    """
    try:
        status = (review_status or "not_required").lower().strip()
        if status not in VALID_REVIEW_STATUSES:
            status = "not_required"

        try:
            confidence = float(agent_response.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0

        response_text = str(
            agent_response.get("response")
            or agent_response.get("final_response")
            or ""
        )

        entry: Dict[str, Any] = {
            "log_id": _new_log_id(),
            "timestamp": _utc_now_iso(),
            "query": query or "",
            "intent": intent or str(agent_response.get("intent", "") or ""),
            "response": response_text,
            "confidence": round(confidence, 2),
            "risk_flags": list(risk_result.get("risk_flags") or []),
            "risk_level": str(risk_result.get("risk_level", "low") or "low").lower(),
            "review_required": bool(risk_result.get("review_required", False)),
            "review_status": status,
            "ticket_id": ticket_id,
            "review_id": review_id,
            "sources": list(agent_response.get("sources") or []),
        }

        logs = load_audit_logs()
        logs.append(entry)

        if not save_audit_logs(logs):
            return _error_result("Failed to persist audit log entry.")

        return _success_result(
            "Interaction logged.",
            log_id=entry["log_id"],
            data=entry,
        )
    except Exception as exc:  # noqa: BLE001 — router must not crash on logging
        logger.exception("log_interaction failed: %s", exc)
        return _error_result(f"Audit logging failed: {type(exc).__name__}")


def get_audit_logs() -> List[Dict[str, Any]]:
    """
    Return all audit log entries (newest last).

    Returns:
        List of log dicts; empty list if none or on load failure.
    """
    try:
        return load_audit_logs()
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_audit_logs failed: %s", exc)
        return []


def get_audit_summary() -> Dict[str, Any]:
    """
    Compute summary statistics over all audit logs.

    Returns:
        Dict with ``total_logs``, review counts, ``average_confidence``,
        and ``risk_level_counts`` (low/medium/high).
    """
    logs = get_audit_logs()

    summary: Dict[str, Any] = {
        "total_logs": len(logs),
        "review_required_count": 0,
        "auto_approved_count": 0,
        "pending_review_count": 0,
        "average_confidence": 0.0,
        "risk_level_counts": {"low": 0, "medium": 0, "high": 0},
    }

    if not logs:
        return summary

    confidence_total = 0.0
    confidence_count = 0

    for entry in logs:
        if entry.get("review_required"):
            summary["review_required_count"] += 1
        else:
            summary["auto_approved_count"] += 1

        status = str(entry.get("review_status", "") or "").lower()
        if status == "pending":
            summary["pending_review_count"] += 1

        level = str(entry.get("risk_level", "low") or "low").lower()
        if level in summary["risk_level_counts"]:
            summary["risk_level_counts"][level] += 1
        else:
            summary["risk_level_counts"]["low"] += 1

        try:
            confidence_total += float(entry.get("confidence", 0.0) or 0.0)
            confidence_count += 1
        except (TypeError, ValueError):
            pass

    if confidence_count:
        summary["average_confidence"] = round(confidence_total / confidence_count, 2)

    return summary


# ---------------------------------------------------------------------------
# Legacy scaffold API
# ---------------------------------------------------------------------------


def log_event(event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Append a generic audit event (legacy helper).

    Wraps ``log_interaction`` when *payload* contains interaction fields;
    otherwise stores a minimal event record.

    Returns:
        True if logging succeeded, False otherwise.
    """
    try:
        if "agent_response" in payload and "risk_result" in payload:
            result = log_interaction(
                query=str(payload.get("query", "")),
                intent=str(payload.get("intent", event_type)),
                agent_response=payload["agent_response"],
                risk_result=payload["risk_result"],
                review_status=str(payload.get("review_status", "not_required")),
                ticket_id=payload.get("ticket_id"),
                review_id=payload.get("review_id"),
            )
            return bool(result.get("success"))

        entry = {
            "log_id": _new_log_id(),
            "timestamp": _utc_now_iso(),
            "query": str(payload.get("query", "")),
            "intent": str(payload.get("intent", event_type)),
            "response": str(payload.get("response", "")),
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "risk_flags": list(payload.get("risk_flags") or []),
            "risk_level": str(payload.get("risk_level", "low") or "low").lower(),
            "review_required": bool(payload.get("review_required", False)),
            "review_status": str(payload.get("review_status", "not_required")),
            "ticket_id": payload.get("ticket_id"),
            "review_id": payload.get("review_id"),
            "sources": list(payload.get("sources") or []),
            "event_type": event_type,
        }

        logs = load_audit_logs()
        logs.append(entry)
        return save_audit_logs(logs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("log_event failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import json as _json
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))

    from middleware.risk_rules import check_risk

    print("BuildWise audit logger — test run\n")

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

    # Use a clean log file for deterministic demo output
    save_audit_logs([])

    print("1. Logging Tower B delay interaction...")
    log_result = log_interaction(
        query=sample_query,
        intent="construction_status",
        agent_response=sample_agent,
        risk_result=sample_risk,
        review_status="pending",
        review_id="REV-DEMO001",
    )
    print(f"   success : {log_result['success']}")
    print(f"   log_id  : {log_result.get('log_id')}")
    print(f"   message : {log_result['message']}")

    print("\n2. Latest log entry:")
    all_logs = get_audit_logs()
    latest = all_logs[-1] if all_logs else {}
    print(_json.dumps(latest, indent=2))

    print("\n3. Audit summary:")
    summary = get_audit_summary()
    print(_json.dumps(summary, indent=2))

    assert log_result["success"] is True
    assert latest.get("query") == sample_query
    assert latest.get("review_required") is True
    assert latest.get("review_status") == "pending"
    assert summary["total_logs"] >= 1
    assert summary["review_required_count"] >= 1
    assert summary["pending_review_count"] >= 1
    assert summary["risk_level_counts"]["high"] >= 1

    print("\nAll audit logger checks: PASS")
