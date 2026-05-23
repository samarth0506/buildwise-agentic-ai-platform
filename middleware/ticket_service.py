"""
BuildWise ticket service — support ticket persistence for tracked issues.

Stores tickets in ``data/tickets.json`` for maintenance, escalation, payment,
legal, safety, and high-risk construction cases that need operational follow-up.

Typical flow::

    flags = normalize_risk_flags(agent_response.get("risk_flags", []))
    if should_create_ticket(intent, flags):
        create_ticket(query, intent, agent_response)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TICKETS_PATH = PROJECT_ROOT / "data" / "tickets.json"

VALID_PRIORITIES = frozenset({"low", "medium", "high", "critical"})
VALID_STATUSES = frozenset({"open", "in_progress", "resolved", "closed"})
OPEN_STATUSES = frozenset({"open", "in_progress"})

# Intents / flags that warrant a support ticket
TICKET_INTENTS = frozenset({"maintenance_issue", "escalation"})
TICKET_RISK_FLAGS = frozenset(
    {
        "payment_dispute",
        "legal_issue",
        "safety_issue",
        "maintenance_urgent",
        "high_risk",
        "construction_delay",
        "escalation_required",
        "angry_customer",
    }
)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_data_dir() -> None:
    """Create ``data/`` if it does not exist."""
    TICKETS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _new_ticket_id() -> str:
    """Generate a unique ticket identifier."""
    return f"TKT-{uuid.uuid4().hex[:8].upper()}"


def _success_result(
    message: str,
    *,
    ticket_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": True, "message": message}
    if ticket_id is not None:
        result["ticket_id"] = ticket_id
    if data is not None:
        result["data"] = data
    return result


def _error_result(message: str, *, ticket_id: Optional[str] = None) -> Dict[str, Any]:
    result: Dict[str, Any] = {"success": False, "message": message}
    if ticket_id is not None:
        result["ticket_id"] = ticket_id
    return result


def load_tickets() -> List[Dict[str, Any]]:
    """
    Load all tickets from ``data/tickets.json``.

    Returns an empty list when the file is missing, empty, or corrupted.
    """
    _ensure_data_dir()

    if not TICKETS_PATH.is_file() or TICKETS_PATH.stat().st_size == 0:
        return []

    try:
        raw = TICKETS_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        logger.warning("tickets.json root is not a list; using []")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load tickets (%s); using []", exc)
        return []


def save_tickets(tickets: List[Dict[str, Any]]) -> bool:
    """
    Persist tickets to disk.

    Args:
        tickets: List of ticket dicts.

    Returns:
        True on success, False on write failure.
    """
    _ensure_data_dir()
    try:
        TICKETS_PATH.write_text(
            json.dumps(tickets, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.error("Failed to save tickets: %s", exc)
        return False


def _find_ticket_index(tickets: List[Dict[str, Any]], ticket_id: str) -> int:
    """Return index of *ticket_id* in *tickets*, or ``-1`` if not found."""
    for index, ticket in enumerate(tickets):
        if ticket.get("ticket_id") == ticket_id:
            return index
    return -1


def _normalize_flags(risk_flags: Sequence[Any]) -> List[str]:
    """Canonicalize risk flags via ``risk_rules`` when available."""
    try:
        from middleware.risk_rules import normalize_risk_flags

        return normalize_risk_flags(risk_flags)
    except Exception:  # noqa: BLE001 — keep ticket service resilient
        return [str(f).lower().strip() for f in risk_flags if f]


def _summarize_response(agent_response: Dict[str, Any], max_len: int = 220) -> str:
    """Build a short summary from the agent response text."""
    text = str(
        agent_response.get("response")
        or agent_response.get("final_response")
        or ""
    ).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------


def should_create_ticket(intent: str, risk_flags: Sequence[str]) -> bool:
    """
    Return True when a support ticket should be opened.

    Tickets are created for maintenance/escalation intents and for risk flags
    such as payment disputes, legal issues, safety concerns, urgent maintenance,
    high-risk construction delays, etc.
    """
    intent_key = (intent or "").lower().strip()
    flags = set(_normalize_flags(risk_flags))

    if intent_key in TICKET_INTENTS:
        return True

    if flags & TICKET_RISK_FLAGS:
        return True

    return False


def infer_priority(
    intent: str,
    risk_flags: Sequence[str],
    default: str = "medium",
) -> str:
    """
    Infer ticket priority from intent and risk flags.

    Priority order: critical > high > medium > low.
    """
    intent_key = (intent or "").lower().strip()
    flags = set(_normalize_flags(risk_flags))
    fallback = default if default in VALID_PRIORITIES else "medium"

    if flags & {"safety_issue", "critical_priority"} or "safety" in intent_key:
        return "critical"

    if intent_key == "escalation" or flags & {
        "payment_dispute",
        "legal_issue",
        "escalation_required",
        "angry_customer",
    }:
        return "high"

    if flags & {"maintenance_urgent", "high_risk", "construction_delay"}:
        return "high"

    if intent_key == "maintenance_issue" or flags & {"high_priority_ticket"}:
        return "medium"

    return fallback


def infer_issue_type(intent: str, risk_flags: Sequence[str]) -> str:
    """
    Derive a human-readable issue type label for the ticket.
    """
    intent_key = (intent or "").lower().strip()
    flags = set(_normalize_flags(risk_flags))

    if "safety_issue" in flags:
        return "safety_issue"
    if "payment_dispute" in flags:
        return "payment_dispute"
    if "legal_issue" in flags:
        return "legal_issue"
    if "maintenance_urgent" in flags or intent_key == "maintenance_issue":
        return "maintenance_issue"
    if "construction_delay" in flags or "high_risk" in flags:
        return "construction_concern"
    if intent_key == "escalation" or "escalation_required" in flags:
        return "escalation"
    if intent_key:
        return intent_key
    return "general_inquiry"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_ticket(
    query: str,
    intent: str,
    agent_response: Dict[str, Any],
    priority: str = "medium",
) -> Dict[str, Any]:
    """
    Create and persist a new support ticket.

    Args:
        query: Original user message.
        intent: Routed intent label.
        agent_response: Member 1 agent dict.
        priority: ``low``, ``medium``, ``high``, or ``critical``. When omitted
            or invalid, ``infer_priority`` is used.

    Returns:
        Dict with ``success``, ``message``, ``ticket_id``, and ``data``.
        Never raises.
    """
    try:
        risk_flags = _normalize_flags(agent_response.get("risk_flags") or [])

        if not should_create_ticket(intent, risk_flags):
            return _error_result(
                "Ticket not created: intent and risk flags do not require tracking."
            )

        explicit_priority = (priority or "medium").lower().strip()
        inferred_priority = infer_priority(intent, risk_flags)
        # Default "medium" means auto-infer; explicit low/high/critical is honored
        if explicit_priority == "medium":
            priority_key = inferred_priority
        elif explicit_priority in VALID_PRIORITIES:
            priority_key = explicit_priority
        else:
            priority_key = inferred_priority

        ticket_id = _new_ticket_id()
        ticket: Dict[str, Any] = {
            "ticket_id": ticket_id,
            "timestamp": _utc_now_iso(),
            "query": query or "",
            "intent": (intent or str(agent_response.get("intent", "") or "")).lower(),
            "issue_type": infer_issue_type(intent, risk_flags),
            "priority": priority_key,
            "status": "open",
            "response_summary": _summarize_response(agent_response),
            "risk_flags": risk_flags,
            "sources": list(agent_response.get("sources") or []),
        }

        tickets = load_tickets()
        tickets.append(ticket)

        if not save_tickets(tickets):
            return _error_result("Failed to save ticket to disk.")

        return _success_result(
            "Ticket created.",
            ticket_id=ticket_id,
            data=ticket,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_ticket failed: %s", exc)
        return _error_result(f"Ticket creation failed: {type(exc).__name__}")


def get_all_tickets() -> List[Dict[str, Any]]:
    """Return every ticket (oldest first)."""
    try:
        return load_tickets()
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_all_tickets failed: %s", exc)
        return []


def get_open_tickets() -> List[Dict[str, Any]]:
    """Return tickets with status ``open`` or ``in_progress``."""
    return [
        ticket
        for ticket in get_all_tickets()
        if ticket.get("status") in OPEN_STATUSES
    ]


def update_ticket_status(ticket_id: str, status: str) -> Dict[str, Any]:
    """
    Update a ticket's workflow status.

    Args:
        ticket_id: Existing ticket ID.
        status: One of ``open``, ``in_progress``, ``resolved``, ``closed``.

    Returns:
        Dict with ``success``, ``message``, ``ticket_id``, and ``data``.
    """
    status_key = (status or "").lower().strip()
    if status_key not in VALID_STATUSES:
        return _error_result(
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}.",
            ticket_id=ticket_id,
        )

    tickets = load_tickets()
    index = _find_ticket_index(tickets, ticket_id)
    if index < 0:
        return _error_result(f"Ticket ID not found: {ticket_id}", ticket_id=ticket_id)

    ticket = tickets[index]
    ticket["status"] = status_key
    tickets[index] = ticket

    if not save_tickets(tickets):
        return _error_result("Failed to save ticket update.", ticket_id=ticket_id)

    return _success_result(
        f"Ticket status updated to '{status_key}'.",
        ticket_id=ticket_id,
        data=ticket,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import json as _json
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))

    print("BuildWise ticket service — test run\n")

    save_tickets([])

    maintenance_agent = {
        "intent": "maintenance_issue",
        "response": "Plumbing team assigned for water leakage in unit 1203.",
        "confidence": 0.84,
        "risk_flags": ["high_priority_ticket"],
        "sources": ["maintenance_issues.csv"],
    }

    escalation_agent = {
        "intent": "escalation",
        "response": "Payment dispute escalated to Accounts & Billing.",
        "confidence": 0.75,
        "risk_flags": ["angry_customer", "payment_dispute"],
        "sources": ["mock_escalation_playbook"],
    }

    print('1. Creating maintenance ticket: "Water leakage in apartment 1203"...')
    t1 = create_ticket(
        "Water leakage in apartment 1203",
        "maintenance_issue",
        maintenance_agent,
    )
    print(f"   success    : {t1['success']}")
    print(f"   ticket_id  : {t1.get('ticket_id')}")
    print(f"   issue_type : {t1.get('data', {}).get('issue_type')}")
    print(f"   priority   : {t1.get('data', {}).get('priority')}")

    print('\n2. Creating escalation ticket: "I am angry about my payment dispute"...')
    t2 = create_ticket(
        "I am angry about my payment dispute",
        "escalation",
        escalation_agent,
    )
    print(f"   success    : {t2['success']}")
    print(f"   ticket_id  : {t2.get('ticket_id')}")
    print(f"   issue_type : {t2.get('data', {}).get('issue_type')}")
    print(f"   priority   : {t2.get('data', {}).get('priority')}")

    print("\n3. Open tickets:")
    open_tickets = get_open_tickets()
    print(f"   count: {len(open_tickets)}")
    for ticket in open_tickets:
        print(
            f"   - {ticket['ticket_id']} | {ticket['issue_type']} | "
            f"priority={ticket['priority']} | status={ticket['status']}"
        )

    first_id = t1.get("ticket_id", "")
    print(f"\n4. Updating {first_id} to in_progress...")
    update_result = update_ticket_status(first_id, "in_progress")
    print(f"   success : {update_result['success']}")
    print(f"   message : {update_result['message']}")
    print(f"   status  : {update_result.get('data', {}).get('status')}")

    print("\n5. All tickets snapshot:")
    print(_json.dumps(get_all_tickets(), indent=2))

    assert t1["success"] is True
    assert t2["success"] is True
    assert len(open_tickets) == 2
    assert update_result["success"] is True
    assert update_result["data"]["status"] == "in_progress"
    assert should_create_ticket("maintenance_issue", []) is True
    assert should_create_ticket("property_inquiry", []) is False
    assert infer_priority("escalation", ["payment_dispute"]) == "high"

    print("\nAll ticket service checks: PASS")
