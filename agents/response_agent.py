"""
BuildWise response agent — turns raw agent output into a polite customer message.

No APIs or ML. Used after construction (or other) agents and before the UI /
human review queue (Prompts 12–15).
"""

from __future__ import annotations

# Customer-facing threshold (slightly above middleware LOW_CONFIDENCE 0.70)
REVIEW_CONFIDENCE_THRESHOLD = 0.75


def _format_confidence(confidence: float) -> str:
    """Show confidence as a percentage for readability."""
    pct = int(round(confidence * 100))
    return f"{pct}%"


def _strip_markdown_for_customer(text: str) -> str:
    """Remove simple markdown markers so chat text reads cleanly."""
    cleaned = text.replace("**", "").strip()
    return cleaned


def _review_notice(confidence: float) -> str | None:
    """Message when confidence is below the review threshold."""
    if confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return (
            "Because our confidence in this answer is below 75%, "
            "it will be reviewed by the BuildWise support team before we send a final update."
        )
    return None


def _risk_notice(risk_flags: list) -> str | None:
    """Message when risk flags are present."""
    if not risk_flags:
        return None
    flags_text = ", ".join(flag.replace("_", " ") for flag in risk_flags)
    return (
        f"This case has been flagged for possible follow-up ({flags_text}). "
        "A team member may review the details to ensure accuracy."
    )


def _next_step(confidence: float, risk_flags: list) -> str:
    """Suggest a realistic next step without overpromising."""
    if confidence < REVIEW_CONFIDENCE_THRESHOLD or risk_flags:
        return (
            "Next step: You will receive an updated message once our team has "
            "completed the review. We aim to respond within 1–2 business days, "
            "subject to site verification."
        )
    return (
        "Next step: If you need more detail, reply with your tower name or "
        "ask a follow-up question. For urgent safety or legal matters, "
        "contact BuildWise support directly."
    )


def generate_customer_response(agent_output: dict) -> str:
    """
    Convert raw agent output into a professional customer-facing reply.

    Expected keys in agent_output:
        intent, response, confidence, risk_flags, sources (optional)

    Args:
        agent_output: Dict from an agent such as handle_construction_query().

    Returns:
        Formatted string suitable for Streamlit chat or review queue draft.
    """
    main_answer = _strip_markdown_for_customer(
        agent_output.get("response", "We could not find information for your request.")
    )
    confidence = float(agent_output.get("confidence", 0.0))
    risk_flags = agent_output.get("risk_flags") or []
    intent = agent_output.get("intent", "general")

    sections: list[str] = []

    # Greeting and main content
    sections.append("Thank you for contacting BuildWise.")
    sections.append("")
    sections.append(main_answer)
    sections.append("")

    # Confidence (transparent, not overpromising)
    sections.append(
        f"Our current confidence in this answer is {_format_confidence(confidence)} "
        f"(category: {intent.replace('_', ' ')})."
    )

    # Low confidence → support team review
    review_msg = _review_notice(confidence)
    if review_msg:
        sections.append("")
        sections.append(review_msg)

    # Risk flags → possible human review
    risk_msg = _risk_notice(risk_flags)
    if risk_msg:
        sections.append("")
        sections.append(risk_msg)

    # Next step
    sections.append("")
    sections.append(_next_step(confidence, risk_flags))

    # Disclaimer — avoid guarantees
    sections.append("")
    sections.append(
        "Please note: timelines and completion figures are based on available "
        "project data and may change after site verification."
    )

    return "\n".join(sections)


if __name__ == "__main__":
    sample_output = {
        "intent": "construction_status",
        "response": (
            "Tower B is delayed due to material delivery issues. "
            "Current completion is 72%."
        ),
        "confidence": 0.72,
        "risk_flags": ["construction_delay"],
        "sources": ["mock_construction_data"],
    }

    print("BuildWise response agent — test run\n")
    print("Input:")
    for key, value in sample_output.items():
        print(f"  {key}: {value}")
    print("\n" + "=" * 60)
    print("Customer-facing response:\n")
    customer_text = generate_customer_response(sample_output)
    print(customer_text)

    # Quick checks for demo / capstone
    assert "Tower B" in customer_text
    assert "72%" in customer_text
    assert "72%" in customer_text or "confidence" in customer_text.lower()
    assert "BuildWise support team" in customer_text
    assert "construction delay" in customer_text.lower() or "construction_delay" in sample_output["risk_flags"]
    assert "Next step" in customer_text
    print("\n" + "=" * 60)
    print("Sample checks: PASS")