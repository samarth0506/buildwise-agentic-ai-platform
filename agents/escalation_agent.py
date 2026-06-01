"""
BuildWise escalation agent — handles sensitive complaints and urgent cases.

No APIs or ML. Detects angry, legal, payment, refund, safety, and urgent cases.
"""

from __future__ import annotations

from agents.response_agent import apply_llm_to_agent_result

AGENT_DISPLAY_NAME = "Escalation Agent"

# ---------------------------------------------------------------------------
# Escalation case playbooks
# ---------------------------------------------------------------------------

MOCK_ESCALATION_PLAYBOOKS: dict[str, dict] = {
    "angry_customer": {
        "title": "Angry customer / service complaint",
        "keywords": ["angry", "furious", "unacceptable", "worst", "complaint", "frustrated"],
        "escalation_department": "Customer Relations",
        "default_priority": "high",
        "suggested_action": (
            "Assign a senior relationship manager to call back within 4 business hours. "
            "Acknowledge concerns without admitting liability."
        ),
        "response_intro": (
            "We understand you are unhappy with your experience. "
            "Your message has been escalated to our Customer Relations team."
        ),
        "risk_flags": ["angry_customer", "reputation_risk"],
    },
    "legal_issue": {
        "title": "Legal issue",
        "keywords": ["legal", "lawyer", "court", "notice", "litigation", "sue", "dispute"],
        "escalation_department": "Legal & Compliance",
        "default_priority": "critical",
        "suggested_action": (
            "Route to Legal & Compliance; do not provide legal advice in chat. "
            "Request written notice details and unit reference."
        ),
        "response_intro": (
            "Matters involving legal proceedings require review by our Legal & Compliance team. "
            "We will not discuss case merits in this channel."
        ),
        "risk_flags": ["legal_issue", "compliance_review"],
    },
    "payment_dispute": {
        "title": "Payment dispute",
        "keywords": [
            "payment dispute",
            "overcharged",
            "wrong amount",
            "billing",
            "invoice error",
            "charged twice",
        ],
        "escalation_department": "Accounts & Billing",
        "default_priority": "high",
        "suggested_action": (
            "Freeze disputed line items pending audit; share transaction ID and receipt copies."
        ),
        "response_intro": (
            "Payment disputes are reviewed by Accounts & Billing with finance oversight."
        ),
        "risk_flags": ["payment_dispute", "financial_review"],
    },
    "refund": {
        "title": "Refund request",
        "keywords": ["refund", "money back", "cancel booking", "cancellation"],
        "escalation_department": "Accounts & Sales Leadership",
        "default_priority": "high",
        "suggested_action": (
            "Check booking terms and refund policy; escalate to sales leadership if amount exceeds threshold."
        ),
        "response_intro": (
            "Refund requests are evaluated against your agreement and payment schedule. "
            "Approval is not automatic."
        ),
        "risk_flags": ["refund_request", "financial_review"],
    },
    "safety_concern": {
        "title": "Safety concern",
        "keywords": ["safety", "unsafe", "hazard", "injury", "fire", "gas leak", "emergency"],
        "escalation_department": "Safety & Security",
        "default_priority": "critical",
        "suggested_action": (
            "If there is immediate danger, contact local emergency services first. "
            "Notify on-site security and log critical incident ticket."
        ),
        "response_intro": (
            "Safety concerns are treated as highest priority. "
            "Please ensure you are in a safe location."
        ),
        "risk_flags": ["safety_concern", "immediate_escalation"],
    },
    "urgent_complaint": {
        "title": "Urgent complaint",
        "keywords": ["urgent", "asap", "immediately", "escalate", "priority", "critical"],
        "escalation_department": "Operations Command Desk",
        "default_priority": "critical",
        "suggested_action": (
            "Open priority ticket; operations desk to acknowledge within 2 hours during business hours."
        ),
        "response_intro": (
            "Your request has been flagged as urgent and sent to our Operations Command Desk."
        ),
        "risk_flags": ["urgent_complaint", "sla_breach_risk"],
    },
}

SOURCE_LABEL = "mock_escalation_playbook"
INTENT_LABEL = "escalation"

PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _normalize(query: str) -> str:
    return query.lower().strip()


def _detect_case_types(query: str) -> list[str]:
    """Return playbook keys matching keywords in the user message."""
    text = _normalize(query)
    matched: list[str] = []

    for case_key, entry in MOCK_ESCALATION_PLAYBOOKS.items():
        for keyword in entry["keywords"]:
            if keyword in text:
                if case_key not in matched:
                    matched.append(case_key)
                break

    # "dispute" often pairs with payment unless clearly legal
    if "dispute" in text and "payment_dispute" not in matched and "legal_issue" not in matched:
        if any(w in text for w in ("payment", "bill", "charge", "invoice")):
            matched.append("payment_dispute")
        elif "legal" not in text:
            matched.append("payment_dispute")

    return matched


def _resolve_priority(case_types: list[str], query: str) -> str:
    if not case_types:
        return "high"  # escalation intent itself implies elevated priority

    priorities = [
        MOCK_ESCALATION_PLAYBOOKS[c]["default_priority"] for c in case_types
    ]
    return max(priorities, key=lambda p: PRIORITY_RANK.get(p, 0))


def _resolve_department(case_types: list[str]) -> str:
    if not case_types:
        return "Customer Relations (triage)"
    if len(case_types) == 1:
        return MOCK_ESCALATION_PLAYBOOKS[case_types[0]]["escalation_department"]
    depts = [MOCK_ESCALATION_PLAYBOOKS[c]["escalation_department"] for c in case_types]
    return " / ".join(dict.fromkeys(depts))  # unique, preserve order


def _resolve_suggested_actions(case_types: list[str]) -> str:
    if not case_types:
        return (
            "Log escalation ticket and assign to Customer Relations for classification "
            "within one business day."
        )
    actions = [MOCK_ESCALATION_PLAYBOOKS[c]["suggested_action"] for c in case_types]
    return " ".join(actions) if len(actions) == 1 else " ".join(f"({i+1}) {a}" for i, a in enumerate(actions))


def _collect_risk_flags(case_types: list[str], priority: str) -> list[str]:
    flags: list[str] = []
    seen: set[str] = set()

    for case_key in case_types:
        for flag in MOCK_ESCALATION_PLAYBOOKS[case_key]["risk_flags"]:
            if flag not in seen:
                seen.add(flag)
                flags.append(flag)

    if priority == "critical":
        if "critical_priority" not in seen:
            flags.append("critical_priority")

    if not case_types:
        flags.append("unspecified_escalation")

    return flags


def _compute_confidence(case_types: list[str]) -> float:
    if not case_types:
        return 0.55
    if len(case_types) == 1:
        return 0.82
    return 0.75


def _build_response(
    query: str,
    case_types: list[str],
    priority: str,
    department: str,
    suggested_action: str,
) -> str:
    lines = [
        "**BuildWise — escalation acknowledgment**",
        "",
        "Thank you for raising this with us. Sensitive matters are reviewed by "
        "specialist teams — we cannot resolve legal, refund, or safety outcomes in this chat alone.",
        "",
        f"**Priority:** {priority.upper()}",
        f"**Escalation department:** {department}",
        "",
    ]

    if not case_types:
        lines.append(
            "We could not classify the exact escalation type from your message. "
            "A coordinator will review and route your case."
        )
        lines.append(_summarize_case_types())
        return "\n".join(lines)

    for case_key in case_types:
        entry = MOCK_ESCALATION_PLAYBOOKS[case_key]
        lines.append(f"**{entry['title']}**")
        lines.append(entry["response_intro"])
        lines.append("")

    lines.append(f"**Suggested internal action:** {suggested_action}")
    lines.append(
        "\n**Next step for you:** A team member will contact you using your registered details. "
        "Please avoid sharing passwords or full bank account numbers in chat."
    )
    lines.append(
        "\n*This message is an acknowledgment only — not a final decision on refunds, "
        "legal outcomes, or safety investigations.*"
    )
    return "\n".join(lines)


def _summarize_case_types() -> str:
    lines = ["\n**Escalation categories we handle:**"]
    for entry in MOCK_ESCALATION_PLAYBOOKS.values():
        lines.append(f"- {entry['title']} → {entry['escalation_department']}")
    return "\n".join(lines)


def handle_escalation_query(query: str) -> dict:
    """
    Triage escalation and high-risk customer messages.

    Args:
        query: User message (e.g. "I want a legal dispute and urgent refund")

    Returns:
        dict with intent, response, confidence, priority, risk_flags,
        escalation_department, suggested_action, sources
    """
    if not query or not query.strip():
        return apply_llm_to_agent_result(
            query or "",
            {
                "intent": INTENT_LABEL,
                "response": _summarize_case_types(),
                "confidence": 0.5,
                "priority": "high",
                "risk_flags": ["unspecified_escalation"],
                "escalation_department": "Customer Relations (triage)",
                "suggested_action": (
                    "Request customer ID and unit; assign to Customer Relations queue."
                ),
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    case_types = _detect_case_types(query)
    priority = _resolve_priority(case_types, query)
    department = _resolve_department(case_types)
    suggested_action = _resolve_suggested_actions(case_types)
    risk_flags = _collect_risk_flags(case_types, priority)
    confidence = _compute_confidence(case_types)

    return apply_llm_to_agent_result(
        query,
        {
            "intent": INTENT_LABEL,
            "response": _build_response(
                query, case_types, priority, department, suggested_action
            ),
            "confidence": confidence,
            "priority": priority,
            "risk_flags": risk_flags,
            "escalation_department": department,
            "suggested_action": suggested_action,
            "sources": [SOURCE_LABEL],
        },
        AGENT_DISPLAY_NAME,
    )


if __name__ == "__main__":
    test_cases = [
        (
            "I am very angry about the delay — this is an unacceptable complaint",
            ["angry_customer"],
        ),
        (
            "We are sending a legal notice about the agreement dispute",
            ["legal_issue"],
        ),
        (
            "Payment dispute — I was charged twice on my invoice",
            ["payment_dispute"],
        ),
        (
            "I want a full refund and cancel my booking immediately",
            ["refund"],
        ),
        (
            "There is a gas leak safety emergency on floor 5",
            ["safety_concern"],
        ),
        (
            "Urgent complaint — escalate to management now",
            ["urgent_complaint"],
        ),
        (
            "Urgent legal dispute and refund — safety concern at site",
            ["legal_issue", "refund", "safety_concern", "urgent_complaint"],
        ),
    ]

    print("BuildWise escalation agent — test run\n")

    for q, expected_subset in test_cases:
        result = handle_escalation_query(q)
        detected = _detect_case_types(q)

        print("=" * 60)
        print(f"Q: {q}")
        print(f"detected: {detected}")
        print(f"intent: {result['intent']}")
        print(f"confidence: {result['confidence']}")
        print(f"priority: {result['priority']}")
        print(f"department: {result['escalation_department']}")
        print(f"suggested_action: {result['suggested_action'][:80]}...")
        print(f"risk_flags: {result['risk_flags']}")
        print("-" * 60)
        print(result["response"][:280] + "...\n")

        assert result["intent"] == INTENT_LABEL
        for t in expected_subset:
            assert t in detected, f"Expected {t} in {detected}"

    # Combined critical case
    combo = handle_escalation_query(
        "Urgent legal dispute and refund due to safety issue — angry customer"
    )
    assert combo["priority"] == "critical"
    assert combo["confidence"] <= 1.0
    assert len(combo["risk_flags"]) >= 2

    print("Escalation agent sample checks: PASS")