"""
Shared helpers that connect Streamlit UI pages to Member 2 middleware.

Keeps display formatting in one place so chat, review queue, and dashboard
stay consistent with backend JSON schemas.
"""

from __future__ import annotations

from typing import Any

# Map intent labels to human-readable agent names (review queue has no agent_used field)
INTENT_TO_AGENT: dict[str, str] = {
    "construction_status": "Construction Agent",
    "documentation_support": "Documentation Agent",
    "maintenance_issue": "Maintenance Agent",
    "property_inquiry": "Property Agent",
    "escalation": "Escalation Agent",
}


def agent_name_for_intent(intent: str) -> str:
    """Return a display label for the agent that handles *intent*."""
    key = (intent or "").lower().strip()
    return INTENT_TO_AGENT.get(key, "Response Agent")


def normalize_router_result(result: dict[str, Any]) -> dict[str, Any]:
    """Convert router output to the UI-friendly response shape."""
    review_required = bool(result.get("review_required", False))
    backend_status = str(result.get("status", "") or "").lower()

    if backend_status == "error":
        ui_status = "error"
    elif review_required or backend_status == "pending_review":
        ui_status = "sent_to_review"
    else:
        ui_status = "auto_approved"

    try:
        confidence = float(result.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    normalized = {
        "final_response": (
            result.get("final_response")
            or result.get("response")
            or "No response generated."
        ),
        "intent": result.get("intent", ""),
        "agent_used": result.get("agent_used")
        or agent_name_for_intent(result.get("intent", "")),
        "confidence": confidence,
        "risk_level": str(result.get("risk_level", "low") or "low").title(),
        "risk_flags": list(result.get("risk_flags") or []),
        "sources": list(result.get("sources") or []),
        "status": ui_status,
        "ticket_id": result.get("ticket_id"),
        "review_id": result.get("review_id"),
        "audit_log_id": result.get("audit_log_id"),
    }
    if "llm_used" in result:
        normalized["llm_used"] = bool(result.get("llm_used"))
    if result.get("llm_fallback_reason"):
        normalized["llm_fallback_reason"] = str(result.get("llm_fallback_reason"))
    return normalized


def review_draft_text(item: dict[str, Any]) -> str:
    """Return the best draft text to show/edit for a review item."""
    return str(
        item.get("edited_response")
        or item.get("original_response")
        or item.get("draft_response")
        or ""
    )


def log_review_action(action: str, item: dict[str, Any]) -> bool:
    """
    Append an audit log entry when a reviewer approves, rejects, or edits.

    Uses middleware.audit_logger.log_event so actions survive Streamlit restarts.
    """
    try:
        from middleware.audit_logger import log_event

        status_map = {
            "review_approved": "approved",
            "review_rejected": "rejected",
            "review_edited": "edited",
        }
        return log_event(
            action,
            {
                "query": item.get("query", ""),
                "intent": item.get("intent", ""),
                "response": review_draft_text(item),
                "confidence": item.get("confidence", 0.0),
                "risk_flags": item.get("risk_flags", []),
                "risk_level": item.get("risk_level", "low"),
                "review_required": True,
                "review_status": status_map.get(action, item.get("status", "pending")),
                "review_id": item.get("review_id"),
                "sources": item.get("sources", []),
            },
        )
    except Exception:
        return False
