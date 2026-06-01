"""
BuildWise property agent — answers listing questions using in-file mock data.

No APIs or ML. Later you can move MOCK_LISTINGS to data/listings.csv (Prompt 17).
"""

from __future__ import annotations

from agents.response_agent import apply_llm_to_agent_result

AGENT_DISPLAY_NAME = "Property Agent"

# ---------------------------------------------------------------------------
# Mock property listings
# ---------------------------------------------------------------------------

MOCK_LISTINGS: list[dict] = [
    {
        "id": "BW-201",
        "type": "2BHK",
        "location": "Pune — Hinjewadi",
        "price_lakh": 68,
        "availability": "available",
        "units_left": 4,
        "possession": "Dec 2026",
        "notes": "Mid-floor units with clubhouse access.",
    },
    {
        "id": "BW-202",
        "type": "2BHK",
        "location": "Pune — Baner",
        "price_lakh": 82,
        "availability": "limited",
        "units_left": 2,
        "possession": "Mar 2027",
        "notes": "Corner units with park view.",
    },
    {
        "id": "BW-301",
        "type": "3BHK",
        "location": "Pune — Hinjewadi",
        "price_lakh": 95,
        "availability": "available",
        "units_left": 6,
        "possession": "Dec 2026",
        "notes": "Larger layout near Tower B site office.",
    },
    {
        "id": "BW-302",
        "type": "3BHK",
        "location": "Mumbai — Thane",
        "price_lakh": 145,
        "availability": "waitlist",
        "units_left": 0,
        "possession": "Jun 2027",
        "notes": "High demand; join waitlist for next release.",
    },
    {
        "id": "BW-401",
        "type": "Villa",
        "location": "Pune — Kharadi",
        "price_lakh": 210,
        "availability": "available",
        "units_left": 1,
        "possession": "Sep 2027",
        "notes": "Premium villa plot with private garden.",
    },
]

SOURCE_LABEL = "mock_property_data"
INTENT_LABEL = "property_inquiry"


def _normalize(query: str) -> str:
    return query.lower().strip()


def _detect_bhk(query: str) -> str | None:
    text = _normalize(query)
    if "3bhk" in text or "3 bhk" in text:
        return "3BHK"
    if "2bhk" in text or "2 bhk" in text:
        return "2BHK"
    return None


def _detect_location(query: str) -> str | None:
    """Match location keywords against mock listing locations."""
    text = _normalize(query)
    location_keywords = [
        "hinjewadi",
        "baner",
        "thane",
        "kharadi",
        "pune",
        "mumbai",
    ]
    for keyword in location_keywords:
        if keyword in text:
            return keyword
    return None


def _parse_budget_lakh(query: str) -> float | None:
    """
    Extract a rough budget in lakhs from phrases like 'under 80 lakh' or 'budget 90'.
    Returns None if no budget hint is found.
    """
    text = _normalize(query)
    if "budget" not in text and "lakh" not in text and "price" not in text and "under" not in text:
        return None

    # Simple scan: find numbers before 'lakh' or after 'under'
    words = text.replace(",", " ").split()
    for i, word in enumerate(words):
        if word.replace(".", "").isdigit():
            try:
                value = float(word)
                # If next word suggests lakhs, or value looks like a lakh amount (< 500)
                if i + 1 < len(words) and "lakh" in words[i + 1]:
                    return value
                if "under" in text or "budget" in text:
                    if value < 500:
                        return value
            except ValueError:
                continue
    return None


def _filter_listings(
    bhk: str | None,
    location: str | None,
    max_budget_lakh: float | None,
) -> list[dict]:
    """Return listings that match optional filters."""
    results = MOCK_LISTINGS

    if bhk:
        results = [l for l in results if l["type"].upper() == bhk.upper() or l["type"] == bhk]

    if location:
        results = [l for l in results if location in l["location"].lower()]

    if max_budget_lakh is not None:
        results = [l for l in results if l["price_lakh"] <= max_budget_lakh]

    return results


def _build_risk_flags(listings: list[dict], query: str) -> list[str]:
    flags: list[str] = []
    text = _normalize(query)

    if not listings:
        flags.append("no_matching_listings")

    if any(l["availability"] == "waitlist" for l in listings):
        flags.append("limited_availability")

    if "urgent" in text or "refund" in text:
        flags.append("sensitive_request")

    return flags


def _compute_confidence(listings: list[dict], query: str) -> float:
    """Higher when we found clear matches; lower when vague or empty."""
    if not listings:
        return 0.45
    if len(listings) == 1:
        return 0.88
    if _detect_bhk(query) or _detect_location(query):
        return 0.82
    return 0.75


def _format_listing_line(listing: dict) -> str:
    return (
        f"- {listing['type']} at {listing['location']}: "
        f"₹{listing['price_lakh']}L, {listing['availability']} "
        f"({listing['units_left']} units), possession {listing['possession']}"
    )


def _build_response(query: str, listings: list[dict]) -> str:
    """Build answer covering BHK, budget, location, availability, possession."""
    text = _normalize(query)
    lines: list[str] = ["**BuildWise — property information**"]

    if not listings:
        lines.append(
            "We could not find listings that match your criteria. "
            "Try specifying 2BHK or 3BHK, a location (e.g. Pune Hinjewadi), or a budget in lakhs."
        )
        lines.append("\n**Sample inventory:**")
        for listing in MOCK_LISTINGS[:3]:
            lines.append(_format_listing_line(listing))
        return "\n".join(lines)

    # Main matches
    lines.append(f"\nWe found {len(listings)} matching option(s):\n")
    for listing in listings:
        lines.append(_format_listing_line(listing))
        if listing.get("notes"):
            lines.append(f"  Note: {listing['notes']}")

    # Topic-specific extras
    if any(w in text for w in ("availability", "available", "units")):
        avail_summary = ", ".join(
            f"{l['type']}: {l['availability']} ({l['units_left']} left)" for l in listings
        )
        lines.append(f"\n**Availability:** {avail_summary}")

    if any(w in text for w in ("possession", "timeline", "handover", "ready")):
        poss_summary = ", ".join(f"{l['type']}: {l['possession']}" for l in listings)
        lines.append(f"\n**Possession timeline:** {poss_summary}")

    if any(w in text for w in ("budget", "price", "cost", "lakh")):
        prices = [l["price_lakh"] for l in listings]
        lines.append(
            f"\n**Budget range (matching):** ₹{min(prices)}L – ₹{max(prices)}L"
        )

    if _detect_location(query):
        lines.append(
            "\n**Location:** Filters applied based on your message. "
            "Site visits can be scheduled after shortlisting."
        )

    lines.append(
        "\n**Next step:** Share your preferred BHK and budget to narrow options. "
        "Final pricing and availability are confirmed by our sales team."
    )
    return "\n".join(lines)


def _summarize_all_listings() -> str:
    lines = ["**BuildWise — available properties (overview)**"]
    for listing in MOCK_LISTINGS:
        lines.append(_format_listing_line(listing))
    lines.append(
        "\nAsk about 2BHK/3BHK, location, budget, availability, or possession — "
        "e.g. 'Show 3BHK under 100 lakh in Pune'"
    )
    return "\n".join(lines)


def handle_property_query(query: str) -> dict:
    """
    Answer property inquiries using mock listing data.

    Args:
        query: User message (e.g. "3BHK availability in Pune under 95 lakh")

    Returns:
        dict with keys: intent, response, confidence, risk_flags, sources
    """
    if not query or not query.strip():
        return apply_llm_to_agent_result(
            query or "",
            {
                "intent": INTENT_LABEL,
                "response": _summarize_all_listings(),
                "confidence": 0.5,
                "risk_flags": [],
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    bhk = _detect_bhk(query)
    location = _detect_location(query)
    budget = _parse_budget_lakh(query)

    listings = _filter_listings(bhk, location, budget)

    # No filters detected — show overview with moderate confidence
    if not bhk and not location and budget is None:
        return apply_llm_to_agent_result(
            query,
            {
                "intent": INTENT_LABEL,
                "response": _summarize_all_listings(),
                "confidence": 0.78,
                "risk_flags": [],
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    risk_flags = _build_risk_flags(listings, query)
    confidence = _compute_confidence(listings, query)

    return apply_llm_to_agent_result(
        query,
        {
            "intent": INTENT_LABEL,
            "response": _build_response(query, listings),
            "confidence": confidence,
            "risk_flags": risk_flags,
            "sources": [SOURCE_LABEL],
        },
        AGENT_DISPLAY_NAME,
    )


if __name__ == "__main__":
    test_queries = [
        "Show me 3BHK apartment price and availability in Pune",
        "2BHK under 80 lakh in Baner",
        "What is the possession timeline for 3BHK in Hinjewadi?",
        "Properties in Mumbai",
        "Hello",
    ]

    print("BuildWise property agent — test run\n")
    passed = 0

    for q in test_queries:
        result = handle_property_query(q)
        print("=" * 60)
        print(f"Q: {q}")
        print(f"intent: {result['intent']}")
        print(f"confidence: {result['confidence']}")
        print(f"risk_flags: {result['risk_flags']}")
        print(f"sources: {result['sources']}")
        print("-" * 60)
        print(result["response"][:400] + ("..." if len(result["response"]) > 400 else ""))
        print()

        assert result["intent"] == INTENT_LABEL
        assert "response" in result and result["response"]
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["sources"] == [SOURCE_LABEL]
        passed += 1

    # Targeted checks
    three_bhk = handle_property_query("3BHK availability Pune under 100 lakh")
    assert "3BHK" in three_bhk["response"]
    assert three_bhk["confidence"] >= 0.7

    no_match = handle_property_query("2BHK under 10 lakh in Baner")
    assert "no_matching_listings" in no_match["risk_flags"] or "could not find" in no_match["response"].lower()

    print(f"Basic checks: {passed}/{len(test_queries)} queries returned valid dicts")
    print("Property agent sample checks: PASS")