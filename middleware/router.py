"""
BuildWise middleware router (scaffold).

Member 2 backend — single entry point for chat and API layers:

    from middleware.router import handle_user_query
    result = handle_user_query("Why is Tower B delayed?")

Planned responsibilities (not implemented in this scaffold):
1. Classify intent and route to the correct specialist agent.
2. Normalize agent output into a unified response shape.
3. Apply confidence scoring, risk rules, and HITL review decisions.
4. Log audit events and create tickets when required.
"""

from __future__ import annotations

from typing import Any, Dict


def handle_user_query(query: str) -> Dict[str, Any]:
    """
    Route a user message through the middleware pipeline.

    Placeholder — returns a minimal stub dict until routing is implemented.
    """
    return {
        "final_response": (
            "BuildWise backend scaffold: routing is not implemented yet. "
            "Please try again after Member 2 middleware is wired."
        ),
        "intent": "general_inquiry",
        "agent_used": "Router (scaffold)",
        "confidence": 0.0,
        "risk_level": "Low",
        "risk_flags": [],
        "sources": [],
        "status": "auto_approved",
        "ticket_id": None,
        "query": query,
    }
