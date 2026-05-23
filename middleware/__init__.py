"""
BuildWise middleware package.

Orchestration, confidence scoring, risk rules, HITL, tickets, and audit logging.
"""

from middleware.audit_logger import log_event
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
from middleware.ticket_service import create_ticket

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
    "get_pending_reviews",
    "handle_user_query",
    "has_low_confidence",
    "is_low_confidence",
    "log_event",
    "normalize_risk_flags",
    "reject_response",
    "should_send_to_review",
]
