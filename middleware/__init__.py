"""
BuildWise middleware package.

Orchestration, confidence scoring, risk rules, HITL, tickets, and audit logging.
"""

from middleware.audit_logger import log_event
from middleware.confidence import calculate_confidence, is_low_confidence
from middleware.hitl_service import append_review_item, should_send_to_review
from middleware.risk_rules import derive_risk_level
from middleware.router import handle_user_query
from middleware.ticket_service import create_ticket

__all__ = [
    "append_review_item",
    "calculate_confidence",
    "create_ticket",
    "derive_risk_level",
    "handle_user_query",
    "is_low_confidence",
    "log_event",
    "should_send_to_review",
]
