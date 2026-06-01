"""
BuildWise documentation agent — answers paperwork questions from hardcoded FAQ.

No APIs or ML. Covers KYC, booking, registration, loans, receipts, and handover.
"""

from __future__ import annotations

from agents.response_agent import apply_llm_to_agent_result

AGENT_DISPLAY_NAME = "Documentation Agent"

# ---------------------------------------------------------------------------
# Hardcoded FAQ entries (expand or move to data/ files later)
# ---------------------------------------------------------------------------

MOCK_FAQ: dict[str, dict] = {
    "kyc": {
        "title": "KYC documents",
        "keywords": ["kyc", "identity", "pan", "aadhaar", "id proof"],
        "summary": (
            "For KYC you typically need: government photo ID (Aadhaar/passport), "
            "PAN card, passport-size photos, and address proof."
        ),
        "steps": [
            "Submit copies at the BuildWise sales office or secure upload portal.",
            "Verification usually takes 2–3 business days.",
            "You will receive email confirmation once KYC is approved.",
        ],
        "timeline": "2–3 business days after complete submission",
        "contact": "documentation@buildwise.example",
    },
    "booking_form": {
        "title": "Booking form",
        "keywords": ["booking", "booking form", "application form", "unit booking"],
        "summary": (
            "The booking form reserves your unit and records buyer details, "
            "chosen unit ID, and initial payment plan."
        ),
        "steps": [
            "Complete the booking form with unit details and co-applicant info (if any).",
            "Pay the booking amount as per the payment schedule.",
            "Sign and submit the form; sales team issues a booking acknowledgment.",
        ],
        "timeline": "Acknowledgment within 1 business day of payment clearance",
        "contact": "sales@buildwise.example",
    },
    "agreement_registration": {
        "title": "Agreement & registration",
        "keywords": [
            "agreement",
            "registration",
            "sale deed",
            "stamp duty",
            "register",
        ],
        "summary": (
            "After booking, the sale agreement is drafted for legal registration. "
            "Stamp duty and registration charges apply as per state rules."
        ),
        "steps": [
            "Review draft sale agreement with your legal advisor if needed.",
            "Schedule registration appointment at the sub-registrar office.",
            "Pay stamp duty and registration fees; collect registered agreement copy.",
        ],
        "timeline": "Usually 2–4 weeks after KYC and payment milestones are met",
        "contact": "legal@buildwise.example",
    },
    "loan_documents": {
        "title": "Loan documents",
        "keywords": ["loan", "home loan", "sanction", "bank", "mortgage", "emi"],
        "summary": (
            "If you use a home loan, the bank needs property papers, KYC, "
            "income proof, and BuildWise NOC / payment schedule."
        ),
        "steps": [
            "Share BuildWise cost sheet and booking acknowledgment with your bank.",
            "Submit income proof, bank statements, and property documents as requested.",
            "Bank issues sanction letter; disbursement follows construction-linked stages.",
        ],
        "timeline": "Sanction letter often within 7–14 days (bank-dependent)",
        "contact": "loans@buildwise.example",
    },
    "payment_receipts": {
        "title": "Payment receipts",
        "keywords": ["receipt", "payment", "invoice", "paid", "transaction"],
        "summary": (
            "Payment receipts confirm amounts received against booking, "
            "construction-linked plans, or other charges."
        ),
        "steps": [
            "Pay via approved channels (cheque, NEFT, portal — per your offer letter).",
            "Receipt is emailed and available in the customer portal within 2 business days.",
            "Keep receipts for loan disbursement and tax records.",
        ],
        "timeline": "Receipt issued within 2 business days of payment posting",
        "contact": "accounts@buildwise.example",
    },
    "handover_documents": {
        "title": "Handover documents",
        "keywords": ["handover", "possession letter", "occupancy", "move in", "keys"],
        "summary": (
            "At handover you receive possession-related documents, "
            "completion certificate copies, and maintenance guidelines."
        ),
        "steps": [
            "Complete final payment and snag-list sign-off.",
            "Collect possession letter, fit-out guidelines, and society bylaws (if applicable).",
            "Register for utilities and society membership as advised on site.",
        ],
        "timeline": "Issued on scheduled possession date after final clearance",
        "contact": "handover@buildwise.example",
    },
}

SOURCE_LABEL = "mock_documentation_faq"
INTENT_LABEL = "documentation_support"

# Map user-facing topics to FAQ keys
TOPIC_ALIASES: dict[str, str] = {
    "kyc": "kyc",
    "booking": "booking_form",
    "booking form": "booking_form",
    "agreement": "agreement_registration",
    "registration": "agreement_registration",
    "loan": "loan_documents",
    "receipt": "payment_receipts",
    "payment": "payment_receipts",
    "handover": "handover_documents",
    "possession": "handover_documents",
}


def _normalize(query: str) -> str:
    return query.lower().strip()


def _detect_topics(query: str) -> list[str]:
    """
    Return FAQ keys that match keywords in the query.
    Returns empty list if no specific topic is detected.
    """
    text = _normalize(query)
    matched: list[str] = []

    for faq_key, entry in MOCK_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in text:
                if faq_key not in matched:
                    matched.append(faq_key)
                break

    # Also check short aliases (e.g. "loan" -> loan_documents)
    for alias, faq_key in TOPIC_ALIASES.items():
        if alias in text and faq_key not in matched:
            matched.append(faq_key)

    return matched


def _build_risk_flags(topics: list[str], query: str) -> list[str]:
    flags: list[str] = []
    text = _normalize(query)

    if not topics:
        flags.append("topic_unclear")

    if any(w in text for w in ("urgent", "legal", "dispute", "complaint")):
        flags.append("sensitive_request")

    if "handover" in text and "delay" in text:
        flags.append("handover_delay_concern")

    return flags


def _compute_confidence(topics: list[str]) -> float:
    if not topics:
        return 0.55
    if len(topics) == 1:
        return 0.86
    return 0.80  # multiple topics — still good but slightly lower


def _format_faq_answer(faq_key: str) -> str:
    entry = MOCK_FAQ[faq_key]
    lines = [
        f"**{entry['title']}**",
        entry["summary"],
        "",
        "**Steps:**",
    ]
    for i, step in enumerate(entry["steps"], start=1):
        lines.append(f"{i}. {step}")
    lines.append(f"\n**Typical timeline:** {entry['timeline']}")
    lines.append(f"**Contact:** {entry['contact']}")
    return "\n".join(lines)


def _summarize_all_topics() -> str:
    lines = ["**BuildWise — documentation help (overview)**", ""]
    for key, entry in MOCK_FAQ.items():
        lines.append(f"- {entry['title']}: {entry['summary'][:80]}...")
    lines.append(
        "\nAsk about KYC, booking form, agreement registration, loan documents, "
        "payment receipts, or handover documents."
    )
    return "\n".join(lines)


def _build_response(query: str, topics: list[str]) -> str:
    text = _normalize(query)
    lines: list[str] = ["**BuildWise — documentation support**", ""]

    if len(topics) == 1:
        lines.append(_format_faq_answer(topics[0]))
    else:
        lines.append(f"We found {len(topics)} relevant topic(s) for your question:\n")
        for topic in topics:
            lines.append(_format_faq_answer(topic))
            lines.append("")

    if "document" in text and not topics:
        lines.append(
            "Please specify which document type you need help with "
            "(KYC, booking, agreement, loan, receipt, or handover)."
        )

    lines.append(
        "\n**Next step:** Gather the listed documents and contact the team email above. "
        "Final requirements may vary by unit and bank — our team will confirm."
    )
    return "\n".join(lines)


def handle_documentation_query(query: str) -> dict:
    """
    Answer documentation and paperwork questions using FAQ data.

    Args:
        query: User message (e.g. "What KYC documents do I need?")

    Returns:
        dict with intent, response, confidence, risk_flags, sources
    """
    if not query or not query.strip():
        return apply_llm_to_agent_result(
            query or "",
            {
                "intent": INTENT_LABEL,
                "response": _summarize_all_topics(),
                "confidence": 0.5,
                "risk_flags": [],
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    topics = _detect_topics(query)

    if not topics:
        return apply_llm_to_agent_result(
            query,
            {
                "intent": INTENT_LABEL,
                "response": _summarize_all_topics(),
                "confidence": _compute_confidence([]),
                "risk_flags": _build_risk_flags([], query),
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    return apply_llm_to_agent_result(
        query,
        {
            "intent": INTENT_LABEL,
            "response": _build_response(query, topics),
            "confidence": _compute_confidence(topics),
            "risk_flags": _build_risk_flags(topics, query),
            "sources": [SOURCE_LABEL],
        },
        AGENT_DISPLAY_NAME,
    )


if __name__ == "__main__":
    test_queries = [
        "image.png",
        "How do I complete the booking form?",
        "Agreement registration and stamp duty process",
        "Home loan documents for bank sanction",
        "I need my payment receipt for last installment",
        "Handover documents at possession",
        "Help with documents",  # vague — overview
        "Urgent legal complaint about registration",  # sensitive flags
    ]

    print("BuildWise documentation agent — test run\n")

    for q in test_queries:
        result = handle_documentation_query(q)
        print("=" * 60)
        print(f"Q: {q}")
        print(f"intent: {result['intent']}")
        print(f"confidence: {result['confidence']}")
        print(f"risk_flags: {result['risk_flags']}")
        print(f"sources: {result['sources']}")
        print("-" * 60)
        preview = result["response"][:350]
        print(preview + ("..." if len(result["response"]) > 350 else ""))
        print()

    # Focused assertions
    kyc = handle_documentation_query("KYC documents list")
    assert kyc["intent"] == INTENT_LABEL
    assert "KYC" in kyc["response"] or "kyc" in kyc["response"].lower()
    assert kyc["confidence"] >= 0.8

    vague = handle_documentation_query("Help with documents")
    assert "topic_unclear" in vague["risk_flags"] or "overview" in vague["response"].lower()

    sensitive = handle_documentation_query("Urgent legal dispute on agreement registration")
    assert "sensitive_request" in sensitive["risk_flags"]

    print("Documentation agent sample checks: PASS")