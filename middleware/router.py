"""
BuildWise middleware router — main orchestrator for chat and API layers.

Single entry point::

    from middleware.router import handle_user_query
    result = handle_user_query("Why is Tower B delayed?")

Pipeline: classify intent → specialist agent → customer response → risk check
→ review queue / tickets → audit log → unified response dict.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.construction_agent import handle_construction_query
from agents.documentation_agent import handle_documentation_query
from agents.escalation_agent import handle_escalation_query
from agents.intent_classifier import classify_intent
from agents.maintenance_agent import handle_maintenance_query
from agents.property_agent import handle_property_query
from agents.response_agent import generate_customer_response

from middleware.audit_logger import log_interaction
from middleware.hitl_service import add_to_queue
from middleware.risk_rules import check_risk
from middleware.ticket_service import create_ticket, infer_priority, should_create_ticket

logger = logging.getLogger(__name__)

# intent → (handler callable, display name for UI)
AGENT_REGISTRY: Dict[str, tuple[Callable[[str], dict], str]] = {
    "property_inquiry": (handle_property_query, "Property Agent"),
    "construction_status": (handle_construction_query, "Construction Agent"),
    "documentation_support": (handle_documentation_query, "Documentation Agent"),
    "maintenance_issue": (handle_maintenance_query, "Maintenance Agent"),
    "escalation": (handle_escalation_query, "Escalation Agent"),
}

FALLBACK_INTENT = "escalation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_agent_handler(intent: str) -> Callable[[str], dict]:
    """
    Return the specialist agent handler for *intent*.

    Unknown intents safely fall back to the escalation agent.
    """
    key = (intent or "").lower().strip()
    handler, _ = AGENT_REGISTRY.get(key, AGENT_REGISTRY[FALLBACK_INTENT])
    return handler


def get_agent_name(intent: str) -> str:
    """Return the human-readable agent label for *intent*."""
    key = (intent or "").lower().strip()
    _, name = AGENT_REGISTRY.get(key, AGENT_REGISTRY[FALLBACK_INTENT])
    return name


def normalize_agent_response(
    agent_response: Dict[str, Any],
    fallback_intent: str,
) -> Dict[str, Any]:
    """
    Normalize Member 1 agent output to the router's internal schema.

    Ensures keys: intent, response, confidence, risk_flags, sources.
    """
    try:
        confidence = float(agent_response.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))

    intent = str(agent_response.get("intent") or fallback_intent or FALLBACK_INTENT)
    response = str(
        agent_response.get("response")
        or agent_response.get("final_response")
        or "We could not generate a response for your request."
    )

    risk_flags = agent_response.get("risk_flags")
    if not isinstance(risk_flags, list):
        risk_flags = list(risk_flags) if risk_flags else []

    sources = agent_response.get("sources")
    if not isinstance(sources, list):
        sources = list(sources) if sources else []

    normalized: Dict[str, Any] = {
        "intent": intent,
        "response": response,
        "confidence": round(confidence, 2),
        "risk_flags": [str(f) for f in risk_flags if f is not None],
        "sources": [str(s) for s in sources if s is not None],
    }
    if "llm_used" in agent_response:
        normalized["llm_used"] = bool(agent_response.get("llm_used"))
    if agent_response.get("llm_fallback_reason"):
        normalized["llm_fallback_reason"] = str(agent_response.get("llm_fallback_reason"))
    return normalized


def build_error_response(query: str, error_message: str) -> Dict[str, Any]:
    """Build a unified error response when the query or pipeline fails."""
    return {
        "query": query or "",
        "intent": "error",
        "agent_used": "Router",
        "response": error_message,
        "final_response": error_message,
        "confidence": 0.0,
        "risk_flags": ["router_error"],
        "risk_level": "low",
        "sources": [],
        "review_required": False,
        "review_id": None,
        "ticket_id": None,
        "audit_log_id": None,
        "status": "error",
    }


def _safe_call_agent(handler: Callable[[str], dict], query: str, intent: str) -> Dict[str, Any]:
    """Invoke an agent handler; return a fallback dict on failure."""
    try:
        raw = handler(query)
        if not isinstance(raw, dict):
            raise TypeError(f"Agent returned {type(raw).__name__}, expected dict")
        return normalize_agent_response(raw, fallback_intent=intent)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent handler failed for intent=%s: %s", intent, exc)
        return normalize_agent_response(
            {
                "intent": intent,
                "response": (
                    "The specialist agent could not process your request. "
                    "A human reviewer will follow up shortly."
                ),
                "confidence": 0.4,
                "risk_flags": ["agent_error"],
                "sources": [],
            },
            fallback_intent=intent,
        )


def _safe_generate_customer_response(agent_response: Dict[str, Any]) -> str:
    """Wrap ``generate_customer_response`` so router never crashes."""
    try:
        return generate_customer_response(agent_response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_customer_response failed: %s", exc)
        return agent_response.get("response", "Thank you for contacting BuildWise.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def handle_user_query(query: str) -> Dict[str, Any]:
    """
    Route a user message through the full middleware pipeline.

    Args:
        query: Raw user message from chat or API.

    Returns:
        Unified response dict for Member 3 UI and audit systems.
    """
    query_text = (query or "").strip()

    if not query_text:
        return build_error_response(
            query,
            "Please enter a question or message so BuildWise can assist you.",
        )

    # 1. Classify intent
    try:
        intent = classify_intent(query_text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("classify_intent failed: %s", exc)
        intent = FALLBACK_INTENT

    if intent not in AGENT_REGISTRY:
        logger.warning("Unknown intent '%s'; routing to escalation", intent)
        intent = FALLBACK_INTENT

    agent_name = get_agent_name(intent)
    handler = get_agent_handler(intent)

    # 2–4. Route and normalize agent response
    agent_response = _safe_call_agent(handler, query_text, intent)

    # 5. Customer-facing response
    final_response = _safe_generate_customer_response(agent_response)

    # 6. Risk evaluation
    try:
        risk_result = check_risk(agent_response, query_text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("check_risk failed: %s", exc)
        risk_result = {
            "review_required": True,
            "risk_flags": ["risk_check_error"],
            "risk_level": "medium",
            "reason": f"Risk check failed: {type(exc).__name__}",
        }

    review_required = bool(risk_result.get("review_required", False))
    risk_flags: List[str] = list(risk_result.get("risk_flags") or [])
    risk_level = str(risk_result.get("risk_level", "low") or "low").lower()

    review_id: Optional[str] = None
    ticket_id: Optional[str] = None
    audit_log_id: Optional[str] = None
    router_status = "completed"
    audit_review_status = "not_required"

    # 7. Human review queue
    if review_required:
        router_status = "pending_review"
        audit_review_status = "pending"
        try:
            queue_result = add_to_queue(query_text, agent_response, risk_result)
            if queue_result.get("success"):
                review_id = queue_result.get("review_id")
            else:
                logger.warning("add_to_queue failed: %s", queue_result.get("message"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("add_to_queue raised: %s", exc)

    # 8. Support ticket
    try:
        if should_create_ticket(agent_response.get("intent", intent), risk_flags):
            priority = infer_priority(
                agent_response.get("intent", intent),
                risk_flags,
            )
            ticket_result = create_ticket(
                query_text,
                agent_response.get("intent", intent),
                agent_response,
                priority=priority,
            )
            if ticket_result.get("success"):
                ticket_id = ticket_result.get("ticket_id")
            else:
                logger.info("Ticket not created: %s", ticket_result.get("message"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_ticket raised: %s", exc)

    # 9. Audit log (always attempt)
    try:
        audit_result = log_interaction(
            query=query_text,
            intent=agent_response.get("intent", intent),
            agent_response=agent_response,
            risk_result=risk_result,
            review_status=audit_review_status,
            ticket_id=ticket_id,
            review_id=review_id,
        )
        if audit_result.get("success"):
            audit_log_id = audit_result.get("log_id")
        else:
            logger.warning("log_interaction failed: %s", audit_result.get("message"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("log_interaction raised: %s", exc)

    # 10. Unified response
    unified: Dict[str, Any] = {
        "query": query_text,
        "intent": agent_response.get("intent", intent),
        "agent_used": agent_name,
        "response": agent_response.get("response", ""),
        "final_response": final_response,
        "confidence": agent_response.get("confidence", 0.0),
        "risk_flags": risk_flags,
        "risk_level": risk_level,
        "sources": agent_response.get("sources", []),
        "review_required": review_required,
        "review_id": review_id,
        "ticket_id": ticket_id,
        "audit_log_id": audit_log_id,
        "status": router_status,
    }
    if "llm_used" in agent_response:
        unified["llm_used"] = bool(agent_response.get("llm_used"))
    if agent_response.get("llm_fallback_reason"):
        unified["llm_fallback_reason"] = str(agent_response.get("llm_fallback_reason"))
    return unified


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import json as _json
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))

    from middleware.audit_logger import save_audit_logs
    from middleware.hitl_service import save_review_queue
    from middleware.ticket_service import save_tickets

    test_queries = [
        "Why is Tower B delayed?",
        "Water leakage in apartment 1203.",
        "I am angry about my payment dispute.",
        "Show me 2BHK under 90 lakhs in Bangalore.",
        "What documents are pending for registration?",
    ]

    # Clean JSON stores for deterministic demo assertions
    save_review_queue([])
    save_tickets([])
    save_audit_logs([])

    print("BuildWise router — test run\n")
    results: list[Dict[str, Any]] = []

    for q in test_queries:
        result = handle_user_query(q)
        results.append(result)
        print("=" * 72)
        print(f"Q: {q}")
        print(f"  intent          : {result['intent']}")
        print(f"  agent_used      : {result['agent_used']}")
        print(f"  confidence      : {result['confidence']}")
        print(f"  risk_level      : {result['risk_level']}")
        print(f"  risk_flags      : {result['risk_flags']}")
        print(f"  review_required : {result['review_required']}")
        print(f"  review_id       : {result['review_id']}")
        print(f"  ticket_id       : {result['ticket_id']}")
        print(f"  audit_log_id    : {result['audit_log_id']}")
        print(f"  status          : {result['status']}")
        print(f"  final_response  : {result['final_response'][:120]}...")
        print()

    # Expected behavior assertions
    tower_b = results[0]
    assert tower_b["intent"] == "construction_status"
    assert tower_b["status"] == "pending_review"
    assert tower_b["review_id"] is not None
    assert tower_b["audit_log_id"] is not None

    leakage = results[1]
    assert leakage["intent"] == "maintenance_issue"
    assert leakage["ticket_id"] is not None

    dispute = results[2]
    assert dispute["intent"] == "escalation"
    assert dispute["status"] == "pending_review"
    assert dispute["ticket_id"] is not None
    assert dispute["review_id"] is not None

    property_q = results[3]
    assert property_q["intent"] == "property_inquiry"
    assert property_q["status"] == "completed"

    docs = results[4]
    assert docs["intent"] == "documentation_support"

    empty = handle_user_query("")
    assert empty["status"] == "error"

    print("Sample unified response (Tower B):")
    print(_json.dumps(tower_b, indent=2)[:900] + "\n...")
    print("\nAll router checks: PASS")
