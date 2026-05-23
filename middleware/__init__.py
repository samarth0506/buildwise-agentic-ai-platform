"""
BuildWise middleware package.

Orchestration, confidence scoring, risk rules, HITL, tickets, and audit logging.
"""

from middleware.audit_logger import (
    get_audit_logs,
    get_audit_summary,
    log_event,
    log_interaction,
)
from middleware.confidence import calculate_confidence, is_low_confidence
from middleware.hitl_service import (
    add_to_queue,
    append_review_item,
    approve_response,
    edit_response,
    get_pending_reviews,
    reject_response,
    should_send_to_review,
)
from middleware.risk_rules import (
    check_risk,
    derive_risk_level,
    detect_query_risk_flags,
    has_low_confidence,
    normalize_risk_flags,
)
from middleware.router import handle_user_query
from middleware.ticket_service import (
    create_ticket,
    get_all_tickets,
    get_open_tickets,
    infer_priority,
    should_create_ticket,
    update_ticket_status,
)

__all__ = [
    "add_to_queue",
    "append_review_item",
    "approve_response",
    "calculate_confidence",
    "check_risk",
    "create_ticket",
    "derive_risk_level",
    "detect_query_risk_flags",
    "edit_response",
    "get_all_tickets",
    "get_audit_logs",
    "get_audit_summary",
    "get_open_tickets",
    "get_pending_reviews",
    "handle_user_query",
    "has_low_confidence",
    "infer_priority",
    "is_low_confidence",
    "log_event",
    "log_interaction",
    "normalize_risk_flags",
    "reject_response",
    "should_create_ticket",
    "should_send_to_review",
    "update_ticket_status",
]
