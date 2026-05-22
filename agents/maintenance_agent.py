"""
BuildWise maintenance agent — triages resident issues using hardcoded playbooks.

No APIs or ML. Classifies into plumbing, electrical, parking, facility, safety, warranty.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Issue categories and playbooks
# ---------------------------------------------------------------------------

MOCK_ISSUE_PLAYBOOKS: dict[str, dict] = {
    "plumbing": {
        "title": "Plumbing",
        "keywords": [
            "plumbing",
            "leakage",
            "leak",
            "water",
            "pipe",
            "tap",
            "drain",
            "sewage",
        ],
        "summary": (
            "Water leaks and drainage issues are logged for the plumbing team. "
            "Please turn off local water supply if safe to do so."
        ),
        "default_priority": "high",
        "suggested_team": "Plumbing & Sanitary",
        "sla": "Response within 24 hours; emergency leaks prioritized same day",
        "steps": [
            "Note the location (tower, floor, unit) and when the issue started.",
            "Share photos if available via the resident portal.",
            "Avoid using affected fixtures until the team confirms it is safe.",
        ],
    },
    "electrical": {
        "title": "Electrical",
        "keywords": [
            "electrical",
            "power",
            "outage",
            "switch",
            "wiring",
            "fuse",
            "light",
            "short",
        ],
        "summary": (
            "Electrical faults are handled by licensed electricians. "
            "Do not touch exposed wiring or wet electrical panels."
        ),
        "default_priority": "high",
        "suggested_team": "Electrical Maintenance",
        "sla": "Response within 24 hours; safety hazards escalated immediately",
        "steps": [
            "Report whether the issue is unit-wide or common area.",
            "Do not reset breakers repeatedly if tripping persists.",
            "Keep the area clear until inspection is complete.",
        ],
    },
    "parking": {
        "title": "Parking",
        "keywords": [
            "parking",
            "basement",
            "slot",
            "vehicle",
            "car",
            "two-wheeler",
            "sticker",
        ],
        "summary": (
            "Parking requests cover assigned slots, access cards, and basement lighting."
        ),
        "default_priority": "medium",
        "suggested_team": "Facility & Parking Desk",
        "sla": "Response within 2 business days",
        "steps": [
            "Share your registered vehicle number and slot ID if assigned.",
            "For access card issues, visit the front desk with ID proof.",
        ],
    },
    "facility": {
        "title": "Facility / common areas",
        "keywords": [
            "facility",
            "gym",
            "clubhouse",
            "lift",
            "elevator",
            "lobby",
            "garden",
            "cleaning",
            "housekeeping",
            "amenity",
        ],
        "summary": (
            "Common-area and amenity issues are routed to the facilities team."
        ),
        "default_priority": "medium",
        "suggested_team": "Facilities Management",
        "sla": "Response within 2–3 business days",
        "steps": [
            "Describe the amenity or area affected.",
            "Report any recurring maintenance needs for tracking.",
        ],
    },
    "safety": {
        "title": "Safety",
        "keywords": [
            "safety",
            "fire",
            "smoke",
            "hazard",
            "gas",
            "injury",
            "emergency",
            "unsafe",
        ],
        "summary": (
            "Safety concerns are treated as urgent. "
            "For immediate danger, contact local emergency services first."
        ),
        "default_priority": "critical",
        "suggested_team": "Safety & Security",
        "sla": "Immediate triage; on-site inspection as soon as possible",
        "steps": [
            "Move to a safe area if required.",
            "Call security desk and emergency services if there is immediate risk.",
            "Do not re-enter affected areas until cleared by authorities.",
        ],
    },
    "warranty": {
        "title": "Warranty / defects",
        "keywords": [
            "warranty",
            "defect",
            "snag",
            "repair",
            "maintenance",
            "crack",
            "paint",
            "fitting",
            "damaged",
        ],
        "summary": (
            "Defects within the warranty period are reviewed against your "
            "handover checklist and builder warranty terms."
        ),
        "default_priority": "medium",
        "suggested_team": "Warranty & Snag Cell",
        "sla": "Inspection scheduled within 5 business days",
        "steps": [
            "Reference your unit ID and handover date.",
            "List items from the snag list with photos.",
            "Warranty coverage is confirmed after site inspection — not guaranteed upfront.",
        ],
    },
}

SOURCE_LABEL = "mock_maintenance_playbook"
INTENT_LABEL = "maintenance_issue"

# Priority order for comparison (higher index = more urgent)
PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _normalize(query: str) -> str:
    return query.lower().strip()


def _detect_issue_types(query: str) -> list[str]:
    """Return playbook keys that match keywords in the query."""
    text = _normalize(query)
    matched: list[str] = []

    for issue_key, entry in MOCK_ISSUE_PLAYBOOKS.items():
        for keyword in entry["keywords"]:
            if keyword in text:
                if issue_key not in matched:
                    matched.append(issue_key)
                break

    return matched


def _resolve_priority(issue_types: list[str], query: str) -> str:
    """
    Pick the highest priority among matched categories.
    Bump to critical if safety is involved or query mentions emergency.
    """
    text = _normalize(query)

    if not issue_types:
        return "medium"

    priorities = [
        MOCK_ISSUE_PLAYBOOKS[t]["default_priority"] for t in issue_types
    ]
    best = max(priorities, key=lambda p: PRIORITY_RANK.get(p, 0))

    if "emergency" in text or "urgent" in text:
        if PRIORITY_RANK.get(best, 0) < PRIORITY_RANK["high"]:
            best = "high"

    if "safety" in issue_types or "fire" in text or "gas" in text:
        best = "critical"

    if "leak" in text or "leakage" in text and "plumbing" in issue_types:
        if PRIORITY_RANK.get(best, 0) < PRIORITY_RANK["high"]:
            best = "high"

    return best


def _resolve_suggested_team(issue_types: list[str]) -> str:
    """Primary team = first matched; multiple teams joined if needed."""
    if not issue_types:
        return "Customer Support (triage)"

    teams = [MOCK_ISSUE_PLAYBOOKS[t]["suggested_team"] for t in issue_types]
    if len(teams) == 1:
        return teams[0]
    return " + ".join(teams)


def _build_risk_flags(issue_types: list[str], query: str, priority: str) -> list[str]:
    flags: list[str] = []
    text = _normalize(query)

    if not issue_types:
        flags.append("category_unclear")

    if priority in ("high", "critical"):
        flags.append("high_priority_ticket")

    if "safety" in issue_types:
        flags.append("safety_escalation")

    if "warranty" in issue_types and any(w in text for w in ("expired", "denied", "refuse")):
        flags.append("warranty_dispute")

    if "electrical" in issue_types and any(w in text for w in ("spark", "burn", "smoke")):
        flags.append("electrical_hazard")

    return flags


def _compute_confidence(issue_types: list[str]) -> float:
    if not issue_types:
        return 0.50
    if len(issue_types) == 1:
        return 0.84
    return 0.78


def _format_playbook(issue_key: str, priority: str) -> str:
    entry = MOCK_ISSUE_PLAYBOOKS[issue_key]
    lines = [
        f"**{entry['title']}** (priority: {priority})",
        entry["summary"],
        "",
        "**What to do:**",
    ]
    for i, step in enumerate(entry["steps"], start=1):
        lines.append(f"{i}. {step}")
    lines.append(f"\n**Expected SLA:** {entry['sla']}")
    lines.append(f"**Assigned team:** {entry['suggested_team']}")
    return "\n".join(lines)


def _summarize_categories() -> str:
    lines = ["**BuildWise — maintenance & repairs (overview)**", ""]
    for key, entry in MOCK_ISSUE_PLAYBOOKS.items():
        lines.append(
            f"- {entry['title']}: {entry['summary'][:70]}... "
            f"(team: {entry['suggested_team']})"
        )
    lines.append(
        "\nDescribe your issue with keywords like plumbing, electrical, parking, "
        "facility, safety, or warranty/defect."
    )
    return "\n".join(lines)


def _build_response(query: str, issue_types: list[str], priority: str, team: str) -> str:
    lines = [
        "**BuildWise — maintenance request**",
        f"\nPriority: **{priority.upper()}**",
        f"Suggested team: **{team}**",
        "",
    ]

    if not issue_types:
        lines.append(_summarize_categories())
        return "\n".join(lines)

    for issue_key in issue_types:
        lines.append(_format_playbook(issue_key, priority))
        lines.append("")

    lines.append(
        "**Next step:** Your request will be logged for the team above. "
        "You may receive a callback to confirm unit details. "
        "Resolution times depend on site access and parts availability."
    )
    return "\n".join(lines)


def handle_maintenance_query(query: str) -> dict:
    """
    Triage maintenance and facility issues.

    Args:
        query: Resident message (e.g. "Water leakage in Tower B bathroom")

    Returns:
        dict with intent, response, confidence, priority, risk_flags,
        suggested_team, sources
    """
    if not query or not query.strip():
        return {
            "intent": INTENT_LABEL,
            "response": _summarize_categories(),
            "confidence": 0.5,
            "priority": "medium",
            "risk_flags": [],
            "suggested_team": "Customer Support (triage)",
            "sources": [SOURCE_LABEL],
        }

    issue_types = _detect_issue_types(query)
    priority = _resolve_priority(issue_types, query)
    suggested_team = _resolve_suggested_team(issue_types)
    risk_flags = _build_risk_flags(issue_types, query, priority)
    confidence = _compute_confidence(issue_types)

    return {
        "intent": INTENT_LABEL,
        "response": _build_response(query, issue_types, priority, suggested_team),
        "confidence": confidence,
        "priority": priority,
        "risk_flags": risk_flags,
        "suggested_team": suggested_team,
        "sources": [SOURCE_LABEL],
    }


if __name__ == "__main__":
    test_queries = [
        ("Water leakage and plumbing repair in Tower B unit 1204", ["plumbing"]),
        ("Electrical outage in basement parking", ["electrical", "parking"]),
        ("Parking slot sticker not working", ["parking"]),
        ("Gym equipment broken in clubhouse", ["facility"]),
        ("Smoke smell near electrical panel — safety emergency", ["safety", "electrical"]),
        ("Warranty defect on bathroom tiles after handover", ["warranty"]),
        ("General maintenance help", []),
    ]

    print("BuildWise maintenance agent — test run\n")
    passed = 0

    for q, expected_types in test_queries:
        result = handle_maintenance_query(q)
        print("=" * 60)
        print(f"Q: {q}")
        print(f"intent: {result['intent']}")
        print(f"confidence: {result['confidence']}")
        print(f"priority: {result['priority']}")
        print(f"suggested_team: {result['suggested_team']}")
        print(f"risk_flags: {result['risk_flags']}")
        print(f"sources: {result['sources']}")
        print("-" * 60)
        print(result["response"][:320] + "...")
        print()

        assert result["intent"] == INTENT_LABEL
        assert result["priority"] in PRIORITY_RANK
        assert result["suggested_team"]
        assert result["sources"] == [SOURCE_LABEL]

        if expected_types:
            for t in expected_types:
                assert t in _detect_issue_types(q), f"Expected {t} in detected types"
        passed += 1

    # Priority checks
    safety = handle_maintenance_query("Fire safety hazard in lobby")
    assert safety["priority"] == "critical"
    assert "safety_escalation" in safety["risk_flags"]

    vague = handle_maintenance_query("Need help")
    assert "category_unclear" in vague["risk_flags"]

    plumbing = handle_maintenance_query("Plumbing leakage urgent")
    assert plumbing["priority"] in ("high", "critical")

    print(f"Ran {passed} query scenarios")
    print("Maintenance agent sample checks: PASS")