"""
BuildWise risk rules — centralized risk detection for the middleware pipeline.

Combines agent ``risk_flags``, query keyword analysis, and confidence scoring
to decide review requirements for ``middleware/router.py`` and HITL services.

Expected agent response shape (Member 1)::

    {
        "intent": "...",
        "response": "...",
        "confidence": 0.82,
        "risk_flags": [...],
        "sources": [...]
    }

``check_risk`` output shape::

    {
        "review_required": true/false,
        "risk_flags": [...],
        "risk_level": "low" | "medium" | "high",
        "reason": "..."
    }
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIDENCE_THRESHOLD = 0.75

# Canonical risk flag names supported by the platform
CANONICAL_FLAGS = frozenset(
    {
        "construction_delay",
        "low_confidence",
        "payment_dispute",
        "legal_issue",
        "angry_customer",
        "safety_issue",
        "maintenance_urgent",
        "documentation_missing",
        "escalation_required",
        "high_risk",
    }
)

# Map legacy / agent-specific flag names to canonical names
FLAG_ALIASES: Dict[str, str] = {
    "high_risk": "high_risk",
    "medium_risk": "high_risk",  # agent medium project risk → elevated review
    "construction_delay": "construction_delay",
    "legal_issue": "legal_issue",
    "legal_risk": "legal_issue",
    "compliance_review": "legal_issue",
    "payment_dispute": "payment_dispute",
    "refund_request": "payment_dispute",
    "financial_review": "payment_dispute",
    "angry_customer": "angry_customer",
    "reputation_risk": "angry_customer",
    "safety_concern": "safety_issue",
    "safety_escalation": "safety_issue",
    "immediate_escalation": "safety_issue",
    "electrical_hazard": "safety_issue",
    "urgent_complaint": "maintenance_urgent",
    "high_priority_ticket": "maintenance_urgent",
    "topic_unclear": "documentation_missing",
    "handover_delay_concern": "construction_delay",
    "sensitive_request": "escalation_required",
    "unspecified_escalation": "escalation_required",
    "critical_priority": "escalation_required",
    "no_matching_listings": "low_confidence",
}

# Severity tier used for review decisions and risk_level derivation
HIGH_SEVERITY_FLAGS = frozenset(
    {
        "construction_delay",
        "payment_dispute",
        "legal_issue",
        "safety_issue",
        "escalation_required",
        "high_risk",
        "angry_customer",
    }
)

MEDIUM_SEVERITY_FLAGS = frozenset(
    {
        "maintenance_urgent",
        "documentation_missing",
        "low_confidence",
    }
)

# Query keyword rules — checked in order; first match per category only
QUERY_RISK_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("construction_delay", ("delay", "delayed", "late", "postponed")),
    ("payment_dispute", ("payment", "refund", "dispute", "money")),
    ("legal_issue", ("legal", "lawyer", "court", "notice")),
    ("angry_customer", ("angry", "frustrated", "complain", "unacceptable")),
    ("safety_issue", ("fire", "accident", "safety", "danger", "collapse")),
    (
        "maintenance_urgent",
        ("leakage", "water", "electricity", "elevator", "urgent"),
    ),
    ("documentation_missing", ("document", "registration", "kyc", "missing")),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def has_low_confidence(confidence: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
    """
    Return True when *confidence* is strictly below *threshold*.

    Args:
        confidence: Agent confidence score in ``[0.0, 1.0]``.
        threshold: Review threshold (default 0.75).
    """
    try:
        score = float(confidence)
    except (TypeError, ValueError):
        return True
    return score < threshold


def normalize_risk_flags(flags: Iterable[Any]) -> List[str]:
    """
    Normalize, deduplicate, and canonicalize risk flag labels.

    - Lowercases and strips whitespace
    - Replaces spaces/hyphens with underscores
    - Maps known agent aliases to canonical platform flags
    - Preserves first-seen order
    """
    if not flags:
        return []

    normalized: List[str] = []
    seen: set[str] = set()

    for raw in flags:
        if raw is None:
            continue
        token = str(raw).lower().strip().replace("-", "_").replace(" ", "_")
        if not token:
            continue

        canonical = FLAG_ALIASES.get(token, token)
        if canonical not in seen:
            seen.add(canonical)
            normalized.append(canonical)

    return normalized


def detect_query_risk_flags(query: str) -> List[str]:
    """
    Detect risk flags from user query keywords (deterministic substring match).

    Args:
        query: Raw user message.

    Returns:
        Ordered list of canonical flag names (no duplicates).
    """
    text = (query or "").lower().strip()
    if not text:
        return []

    detected: List[str] = []
    seen: set[str] = set()

    for flag_name, keywords in QUERY_RISK_RULES:
        if flag_name in seen:
            continue
        if any(keyword in text for keyword in keywords):
            detected.append(flag_name)
            seen.add(flag_name)

    return detected


def derive_risk_level(risk_flags: Sequence[str], confidence: float = 1.0) -> str:
    """
    Derive overall risk level from combined flags and confidence.

    Rules (highest matching tier wins):
    - ``high`` if any high-severity flag is present
    - ``medium`` if any medium-severity flag is present or confidence < 0.75
    - ``low`` otherwise

    Args:
        risk_flags: Canonical/normalized flag names.
        confidence: Agent confidence score.

    Returns:
        ``"low"``, ``"medium"``, or ``"high"``.
    """
    flags = set(normalize_risk_flags(risk_flags))

    if flags & HIGH_SEVERITY_FLAGS:
        return "high"

    if flags & MEDIUM_SEVERITY_FLAGS or has_low_confidence(confidence):
        return "medium"

    return "low"


def check_risk(agent_response: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    """
    Evaluate combined risk from agent output, query text, and confidence.

    Merges:
    - ``risk_flags`` already on the agent response
    - flags detected from the user query
    - ``low_confidence`` when confidence is below threshold
    - ``escalation_required`` when intent is ``escalation``

    Args:
        agent_response: Member 1 agent dict.
        query: Original user message (optional but recommended).

    Returns:
        Dict with ``review_required``, ``risk_flags``, ``risk_level``, ``reason``.
    """
    intent = str(agent_response.get("intent", "") or "").lower().strip()
    try:
        confidence = float(agent_response.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    agent_flags = normalize_risk_flags(agent_response.get("risk_flags") or [])
    query_flags = normalize_risk_flags(detect_query_risk_flags(query))

    combined: List[str] = []
    seen: set[str] = set()
    for flag in agent_flags + query_flags:
        if flag not in seen:
            seen.add(flag)
            combined.append(flag)

    if has_low_confidence(confidence) and "low_confidence" not in seen:
        combined.append("low_confidence")
        seen.add("low_confidence")

    if intent == "escalation" and "escalation_required" not in seen:
        combined.append("escalation_required")
        seen.add("escalation_required")

    risk_level = derive_risk_level(combined, confidence)
    review_required = _is_review_required(combined, confidence, intent, risk_level)
    reason = _build_reason(combined, confidence, intent, review_required)

    return {
        "review_required": review_required,
        "risk_flags": combined,
        "risk_level": risk_level,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flag_tier(flag: str) -> str:
    """Return severity tier for a canonical flag: high, medium, or low."""
    if flag in HIGH_SEVERITY_FLAGS:
        return "high"
    if flag in MEDIUM_SEVERITY_FLAGS:
        return "medium"
    return "low"


def _is_review_required(
    risk_flags: Sequence[str],
    confidence: float,
    intent: str,
    risk_level: str,
) -> bool:
    """
    Decide if human review is required.

    Review is triggered when any of these hold:
    - confidence below threshold
    - intent is escalation
    - construction_delay flag present
    - payment_dispute, legal_issue, or safety_issue present
    - any medium- or high-severity flag present
  """
    flags = set(normalize_risk_flags(risk_flags))

    if has_low_confidence(confidence):
        return True
    if intent == "escalation":
        return True
    if "construction_delay" in flags:
        return True
    if flags & {"payment_dispute", "legal_issue", "safety_issue"}:
        return True
    if any(_flag_tier(f) in ("medium", "high") for f in flags):
        return True
    if risk_level in ("medium", "high"):
        return True

    return False


def _build_reason(
    risk_flags: Sequence[str],
    confidence: float,
    intent: str,
    review_required: bool,
) -> str:
    """Build a short human-readable explanation of the risk decision."""
    flags = normalize_risk_flags(risk_flags)

    if not review_required:
        return "No review required: confidence and risk signals are within auto-approve limits."

    parts: List[str] = []

    if has_low_confidence(confidence):
        pct = int(round(confidence * 100))
        parts.append(f"confidence below threshold ({pct}%)")

    if intent == "escalation":
        parts.append("escalation intent")

    priority_flags = [
        f for f in flags
        if f in HIGH_SEVERITY_FLAGS or f in MEDIUM_SEVERITY_FLAGS
    ]
    if priority_flags:
        parts.append("flags: " + ", ".join(priority_flags))

    if not parts:
        parts.append("elevated risk level")

    return "Review required: " + "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _demo_agent_response(query: str) -> Dict[str, Any]:
    """Build a representative agent response for demo queries (no agent imports)."""
    text = query.lower()

    if "tower b" in text and "delay" in text:
        return {
            "intent": "construction_status",
            "response": "Tower B is delayed due to material delivery issues.",
            "confidence": 0.72,
            "risk_flags": ["construction_delay", "high_risk"],
            "sources": ["mock_construction_data"],
        }
    if "angry" in text and "payment" in text:
        return {
            "intent": "escalation",
            "response": "Payment dispute escalated to Accounts.",
            "confidence": 0.75,
            "risk_flags": ["angry_customer", "payment_dispute"],
            "sources": ["mock_escalation_playbook"],
        }
    if "leakage" in text or "water" in text:
        return {
            "intent": "maintenance_issue",
            "response": "Plumbing team assigned for water leakage.",
            "confidence": 0.84,
            "risk_flags": ["high_priority_ticket"],
            "sources": ["mock_maintenance_playbook"],
        }
    return {
        "intent": "property_inquiry",
        "response": "Matching 2BHK listings in Bangalore.",
        "confidence": 0.88,
        "risk_flags": [],
        "sources": ["mock_property_data"],
    }


if __name__ == "__main__":
    test_cases = [
        "Why is Tower B delayed?",
        "I am angry about my payment dispute.",
        "Water leakage in apartment 1203.",
        "Show me 2BHK under 90 lakhs in Bangalore.",
    ]

    print("BuildWise risk rules — test run\n")
    passed = 0

    for query in test_cases:
        agent_out = _demo_agent_response(query)
        result = check_risk(agent_out, query)

        print("=" * 70)
        print(f"Q: {query}")
        print(f"  intent          : {agent_out['intent']}")
        print(f"  agent confidence: {agent_out['confidence']}")
        print(f"  agent flags     : {agent_out['risk_flags']}")
        print(f"  query flags     : {detect_query_risk_flags(query)}")
        print(f"  combined flags  : {result['risk_flags']}")
        print(f"  risk_level      : {result['risk_level']}")
        print(f"  review_required : {result['review_required']}")
        print(f"  reason          : {result['reason']}")
        print()

        assert "review_required" in result
        assert "risk_flags" in result
        assert result["risk_level"] in ("low", "medium", "high")
        assert isinstance(result["reason"], str) and result["reason"]
        passed += 1

    # Targeted assertions for capstone demo scenarios
    tower_b = check_risk(_demo_agent_response(test_cases[0]), test_cases[0])
    assert tower_b["review_required"] is True
    assert "construction_delay" in tower_b["risk_flags"]
    assert tower_b["risk_level"] == "high"

    payment = check_risk(_demo_agent_response(test_cases[1]), test_cases[1])
    assert payment["review_required"] is True
    assert "payment_dispute" in payment["risk_flags"]

    leakage = check_risk(_demo_agent_response(test_cases[2]), test_cases[2])
    assert leakage["review_required"] is True
    assert "maintenance_urgent" in leakage["risk_flags"]

    property_q = check_risk(_demo_agent_response(test_cases[3]), test_cases[3])
    assert property_q["review_required"] is False
    assert property_q["risk_level"] == "low"

    # Unit checks for public helpers
    assert has_low_confidence(0.74) is True
    assert has_low_confidence(0.75) is False
    assert normalize_risk_flags(["High-Risk", "construction_delay", "High-Risk"]) == [
        "high_risk",
        "construction_delay",
    ]
    assert derive_risk_level(["documentation_missing"], confidence=0.90) == "medium"
    assert derive_risk_level([], confidence=0.95) == "low"

    print(f"All checks passed ({passed}/{len(test_cases)} scenarios + unit tests)")
