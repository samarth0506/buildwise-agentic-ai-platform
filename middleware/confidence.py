"""
BuildWise confidence scoring — simple rules, no ML.

Used by the middleware pipeline (Prompt 12) to decide if a response
needs human review when combined with agent output and risk flags.
"""

from __future__ import annotations

# Base scores depending on whether the agent found relevant data
BASE_WITH_DATA = 0.85
BASE_WITHOUT_DATA = 0.40

# Penalties applied on top of the base score
PENALTY_RISK_FLAGS = 0.10
PENALTY_SENSITIVE_QUERY = 0.15

# Scores below this threshold trigger human-in-the-loop (Prompt 8 / 14)
LOW_CONFIDENCE_THRESHOLD = 0.70

# Escalation-style words in the user query (overlap with intent_classifier)
SENSITIVE_QUERY_KEYWORDS = [
    "angry",
    "legal",
    "dispute",
    "urgent",
    "refund",
    "safety",
]


def _normalize(query: str) -> str:
    return query.lower().strip()


def _query_has_sensitive_keywords(query: str) -> bool:
    """True if the user message contains escalation-related words."""
    text = _normalize(query)
    return any(keyword in text for keyword in SENSITIVE_QUERY_KEYWORDS)


def _clamp(score: float, low: float = 0.0, high: float = 1.0) -> float:
    """Keep confidence within [0, 1]."""
    return max(low, min(high, score))


def calculate_confidence(query: str, data_found: bool, risk_flags: list) -> float:
    """
    Compute a rule-based confidence score for an agent response.

    Args:
        query: Original user message.
        data_found: True if the agent retrieved matching tower/data.
        risk_flags: List of risk labels (e.g. ["construction_delay", "high_risk"]).

    Returns:
        Float between 0.0 and 1.0.
    """
    score = BASE_WITH_DATA if data_found else BASE_WITHOUT_DATA

    # Any non-empty risk flag list lowers confidence
    if risk_flags:
        score -= PENALTY_RISK_FLAGS

    if _query_has_sensitive_keywords(query):
        score -= PENALTY_SENSITIVE_QUERY

    return round(_clamp(score), 2)


def is_low_confidence(score: float) -> bool:
    """
    Return True if the score should be sent to human review.

    Args:
        score: Output from calculate_confidence (or blended with agent score).

    Returns:
        True when score < LOW_CONFIDENCE_THRESHOLD (0.70).
    """
    return score < LOW_CONFIDENCE_THRESHOLD


if __name__ == "__main__":
    test_cases = [
        # (query, data_found, risk_flags, expected_score, expected_low)
        (
            "Why is Tower B delayed?",
            True,
            ["construction_delay", "high_risk"],
            0.75,  # 0.85 - 0.10
            False,
        ),
        (
            "Why is Tower B delayed?",
            True,
            [],
            0.85,
            False,
        ),
        (
            "Unknown tower status",
            False,
            [],
            0.40,
            True,
        ),
        (
            "I need an urgent legal dispute and refund",
            True,
            ["construction_delay"],
            0.60,  # 0.85 - 0.10 - 0.15
            True,
        ),
        (
            "Tower A completion percentage",
            True,
            [],
            0.85,
            False,
        ),
        (
            "Safety concern on site",
            False,
            ["high_risk"],
            0.15,  # 0.40 - 0.10 - 0.15 -> clamped to 0.15
            True,
        ),
    ]

    print("BuildWise confidence scoring — test run\n")
    passed = 0

    for query, data_found, risk_flags, expected_score, expected_low in test_cases:
        score = calculate_confidence(query, data_found, risk_flags)
        low = is_low_confidence(score)
        score_ok = score == expected_score
        low_ok = low == expected_low
        ok = score_ok and low_ok
        if ok:
            passed += 1
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] score={score} (expected {expected_score}), low={low} (expected {expected_low})")
        print(f"         Q: {query}")
        print(f"         data_found={data_found}, risk_flags={risk_flags}\n")

    print(f"Results: {passed}/{len(test_cases)} passed")

    # Capstone demo: Tower B with data + delay risks → often near review threshold
    demo_score = calculate_confidence(
        "Why is Tower B delayed?",
        data_found=True,
        risk_flags=["construction_delay", "high_risk"],
    )
    print(f"Demo query confidence: {demo_score}")
    print(f"Needs human review (< {LOW_CONFIDENCE_THRESHOLD})? {is_low_confidence(demo_score)}")