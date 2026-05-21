"""
BuildWise intent classifier — simple keyword matching (no ML, no APIs).

Maps a user question to one of five intent labels for agent routing.
"""

# Keywords grouped by intent (lowercase matching)
CONSTRUCTION_STATUS_KEYWORDS = [
    "delay",
    "tower",
    "construction",
    "progress",
    "milestone",
    "possession",
]

PROPERTY_INQUIRY_KEYWORDS = [
    "2bhk",
    "3bhk",
    "price",
    "availability",
    "unit",
    "apartment",
    "villa",
    "location",
]

DOCUMENTATION_SUPPORT_KEYWORDS = [
    "document",
    "kyc",
    "agreement",
    "registration",
    "loan",
    "receipt",
    "handover",
]

MAINTENANCE_ISSUE_KEYWORDS = [
    "leakage",
    "plumbing",
    "electrical",
    "parking",
    "maintenance",
    "repair",
    "defect",
]

ESCALATION_KEYWORDS = [
    "angry",
    "complaint",
    "legal",
    "dispute",
    "urgent",
    "refund",
    "safety",
]

# Check escalation/maintenance before construction so urgent issues win ties.
INTENT_RULES = [
    ("escalation", ESCALATION_KEYWORDS),
    ("maintenance_issue", MAINTENANCE_ISSUE_KEYWORDS),
    ("documentation_support", DOCUMENTATION_SUPPORT_KEYWORDS),
    ("property_inquiry", PROPERTY_INQUIRY_KEYWORDS),
    ("construction_status", CONSTRUCTION_STATUS_KEYWORDS),
]


def _normalize(query: str) -> str:
    """Lowercase and strip whitespace for consistent keyword checks."""
    return query.lower().strip()


def _matches_any(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears as a substring in text."""
    return any(keyword in text for keyword in keywords)


def classify_intent(query: str) -> str:
    """
    Classify the user query into one of five intents using keyword rules.

    Args:
        query: Raw user message from the chatbot.

    Returns:
        One of: property_inquiry, construction_status, documentation_support,
        maintenance_issue, escalation. Defaults to construction_status if no
        keywords match (fits the Tower B demo in prompts.md).
    """
    if not query or not query.strip():
        return "construction_status"

    text = _normalize(query)

    for intent, keywords in INTENT_RULES:
        if _matches_any(text, keywords):
            return intent

    return "construction_status"


if __name__ == "__main__":
    test_queries = [
        ("Why is Tower B delayed?", "construction_status"),
        ("What is the construction progress on milestone 3?", "construction_status"),
        ("Show me 3BHK apartment price and availability in Pune", "property_inquiry"),
        ("I need help with KYC document and sale agreement registration", "documentation_support"),
        ("There is water leakage and a plumbing repair needed", "maintenance_issue"),
        ("This is urgent — I want a legal dispute and refund now", "escalation"),
        ("Hello", "construction_status"),
    ]

    print("BuildWise intent classifier — test run\n")
    passed = 0
    for query, expected in test_queries:
        result = classify_intent(query)
        ok = result == expected
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{status}] {result:25} (expected {expected:25})")
        print(f"         Q: {query}\n")

    print(f"Results: {passed}/{len(test_queries)} passed")