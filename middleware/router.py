"""
BuildWise middleware router.

Single entry point for the chat UI:

    from middleware.router import handle_user_query
    result = handle_user_query("Why is Tower B delayed?")

Responsibilities:
1. Detect the intent from keywords (escalation always wins).
2. Call the matching specialist agent.
3. Normalize the agent's reply into the unified UI shape.
4. Apply human-in-the-loop (HITL) rules:
   - sent_to_review  if confidence < 0.75 OR risk_level == "High"
   - auto_approved   otherwise
5. Generate a ticket_id and append to data/review_queue.json
   whenever the case is sent for human review.

Unified output shape:
{
    "final_response": str,
    "intent":         str,
    "agent_used":     str,
    "confidence":     float,
    "risk_level":     "High" | "Medium" | "Low",
    "risk_flags":     list[str],
    "sources":        list[str],
    "status":         "sent_to_review" | "auto_approved",
    "ticket_id":      str | None,
}
"""

from __future__ import annotations

import json
import os
import random
from datetime import datetime
from typing import Callable

from agents.construction_agent import handle_construction_query
from agents.documentation_agent import handle_documentation_query
from agents.escalation_agent import handle_escalation_query
from agents.maintenance_agent import handle_maintenance_query
from agents.property_agent import handle_property_query

# ---------------------------------------------------------------------------
# Routing keywords (lowercase substring matching). Order matters only for the
# escalation tie-break — see _detect_intent.
# ---------------------------------------------------------------------------

ESCALATION_KEYWORDS = (
    "angry",
    "escalate",
    "escalation",
    "refund",
    "compensation",
    "legal",
    "complaint",
    "dispute",
    "delay again",
    "unacceptable",
    "manager",
)

MAINTENANCE_KEYWORDS = (
    "leakage",
    "plumbing",
    "electrical",
    "lift",
    "parking",
    "repair",
    "maintenance",
    "water",
    "issue",
    "defect",
)

DOCUMENTATION_KEYWORDS = (
    "kyc",
    "document",
    "documents",
    "registration",
    "agreement",
    "loan",
    "pan",
    "aadhaar",
    "id proof",
    "address proof",
    "submit",
    "pending documents",
)

PROPERTY_KEYWORDS = (
    "2bhk",
    "3bhk",
    "flat",
    "apartment",
    "villa",
    "property",
    "price",
    "availability",
    "available",
    "location",
    "amenities",
    "floor plan",
    "budget",
)

CONSTRUCTION_KEYWORDS = (
    "tower",
    "construction",
    "delay",
    "delayed",
    "progress",
    "milestone",
    "completion",
    "possession status",
)

# Intent -> (agent function, display name for UI)
AGENT_REGISTRY: dict[str, tuple[Callable[[str], dict], str]] = {
    "escalation":            (handle_escalation_query,    "Escalation Agent"),
    "maintenance_issue":     (handle_maintenance_query,   "Maintenance Agent"),
    "documentation_support": (handle_documentation_query, "Documentation Agent"),
    "property_inquiry":      (handle_property_query,      "Property Agent"),
    "construction_status":   (handle_construction_query,  "Construction Agent"),
}

# ---------------------------------------------------------------------------
# HITL configuration
# ---------------------------------------------------------------------------

LOW_CONFIDENCE_THRESHOLD = 0.75
MEDIUM_CONFIDENCE_FLOOR = 0.60

HIGH_RISK_TOKENS = frozenset(
    {
        "high_risk",
        "legal_risk",
        "payment_dispute",
        "escalation",
        "construction_delay",
        # Common agent-level high-risk equivalents:
        "legal_issue",
        "safety_concern",
        "safety_escalation",
        "critical_priority",
        "immediate_escalation",
    }
)
MEDIUM_RISK_TOKENS = frozenset({"medium_risk"})

DATA_DIR = "data"
REVIEW_FILE = os.path.join(DATA_DIR, "review_queue.json")


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _normalize(query: str) -> str:
    return (query or "").lower().strip()


def _matches_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _detect_intent(query: str) -> str:
    """
    Decide which agent handles the query.

    Priority (highest first):
      escalation -> maintenance -> documentation -> property -> construction
    Escalation always wins because risky cases must not be auto-answered.
    """
    text = _normalize(query)

    if _matches_any(text, ESCALATION_KEYWORDS):
        return "escalation"
    if _matches_any(text, MAINTENANCE_KEYWORDS):
        return "maintenance_issue"
    if _matches_any(text, DOCUMENTATION_KEYWORDS):
        return "documentation_support"
    if _matches_any(text, PROPERTY_KEYWORDS):
        return "property_inquiry"
    if _matches_any(text, CONSTRUCTION_KEYWORDS):
        return "construction_status"
    return "general_inquiry"


# ---------------------------------------------------------------------------
# HITL helpers
# ---------------------------------------------------------------------------

def _derive_risk_level(risk_flags: list[str], confidence: float) -> str:
    flags = {str(f).lower() for f in (risk_flags or [])}

    if flags & HIGH_RISK_TOKENS:
        return "High"
    if (flags & MEDIUM_RISK_TOKENS) or (
        MEDIUM_CONFIDENCE_FLOOR <= confidence < LOW_CONFIDENCE_THRESHOLD
    ):
        return "Medium"
    return "Low"


def _derive_status(confidence: float, risk_level: str) -> str:
    if confidence < LOW_CONFIDENCE_THRESHOLD or risk_level == "High":
        return "sent_to_review"
    return "auto_approved"


def _new_ticket_id() -> str:
    return f"HR-{random.randint(1000, 9999)}"


def _append_to_review_queue(item: dict) -> bool:
    """Safely append a sent_to_review item to data/review_queue.json."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        existing: list[dict] = []
        if os.path.exists(REVIEW_FILE) and os.path.getsize(REVIEW_FILE) > 0:
            try:
                with open(REVIEW_FILE, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, list):
                    existing = loaded
            except (json.JSONDecodeError, OSError):
                existing = []

        if any(r.get("ticket_id") == item["ticket_id"] for r in existing):
            return False

        existing.append(item)
        with open(REVIEW_FILE, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Fallback for general_inquiry
# ---------------------------------------------------------------------------

def _general_inquiry_response(query: str) -> dict:
    return {
        "intent": "general_inquiry",
        "response": (
            "Thanks for reaching out to BuildWise. Could you share a bit more "
            "detail about your query — for example, mention the tower, unit type, "
            "document, or issue — so we can route it to the right team?"
        ),
        "confidence": 0.55,
        "risk_flags": [],
        "sources": [],
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def handle_user_query(query: str) -> dict:
    """
    Route the query to the correct agent and return the unified UI shape.

    Args:
        query: Raw user message from the chatbot.

    Returns:
        Dict with keys: final_response, intent, agent_used, confidence,
        risk_level, risk_flags, sources, status, ticket_id.
    """
    intent = _detect_intent(query)

    if intent in AGENT_REGISTRY:
        agent_fn, agent_label = AGENT_REGISTRY[intent]
        try:
            raw = agent_fn(query)
        except Exception as exc:
            raw = {
                "intent": intent,
                "response": (
                    "The specialist agent could not process this request "
                    f"({type(exc).__name__}). A human reviewer will follow up."
                ),
                "confidence": 0.4,
                "risk_flags": ["agent_error"],
                "sources": [],
            }
    else:
        agent_label = "Response Agent"
        raw = _general_inquiry_response(query)

    final_response = raw.get("response") or raw.get("final_response") or "No response generated."
    confidence = float(raw.get("confidence", 0.5) or 0.5)
    risk_flags = list(raw.get("risk_flags", []) or [])
    sources = list(raw.get("sources", []) or [])

    risk_level = _derive_risk_level(risk_flags, confidence)
    status = _derive_status(confidence, risk_level)
    ticket_id = _new_ticket_id() if status == "sent_to_review" else None

    result = {
        "final_response": final_response,
        "intent": raw.get("intent", intent),
        "agent_used": agent_label,
        "confidence": round(confidence, 2),
        "risk_level": risk_level,
        "risk_flags": risk_flags,
        "sources": sources,
        "status": status,
        "ticket_id": ticket_id,
    }

    if status == "sent_to_review":
        _append_to_review_queue(
            {
                "ticket_id": ticket_id,
                "query": query,
                "draft_response": final_response,
                "confidence": result["confidence"],
                "risk_level": risk_level.lower(),
                "risk_flags": risk_flags,
                "intent": result["intent"],
                "agent_used": agent_label,
                "sources": sources,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )

    return result


# ---------------------------------------------------------------------------
# Self-test (run with: python -m middleware.router)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    samples = [
        ("Show all tower status",                       "construction_status", "auto_approved"),
        ("Why is Tower B delayed?",                     "construction_status", "sent_to_review"),
        ("What KYC documents do I need to submit?",     "documentation_support", None),
        ("Water leakage in apartment 1203",             "maintenance_issue",   None),
        ("Show me 2BHK under 90 lakhs in Bangalore",    "property_inquiry",    None),
        ("I am angry about my payment dispute",         "escalation",          "sent_to_review"),
    ]

    print("BuildWise router — test run\n")
    for q, expected_intent, expected_status in samples:
        r = handle_user_query(q)
        print("=" * 70)
        print(f"Q: {q}")
        print(f"  intent     : {r['intent']}")
        print(f"  agent_used : {r['agent_used']}")
        print(f"  confidence : {r['confidence']}")
        print(f"  risk_level : {r['risk_level']}")
        print(f"  risk_flags : {r['risk_flags']}")
        print(f"  status     : {r['status']}")
        print(f"  ticket_id  : {r['ticket_id']}")
        ok_intent = r["intent"] == expected_intent
        ok_status = expected_status is None or r["status"] == expected_status
        print(f"  intent ok? {ok_intent}   status ok? {ok_status}")
        print(f"  preview    : {r['final_response'][:140]}...")
        print()
