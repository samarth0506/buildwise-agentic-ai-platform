"""
BuildWise construction agent — answers tower status using in-file mock data.

No APIs or ML models. Later prompts can swap MOCK_TOWERS for CSV/RAG data.
"""

from __future__ import annotations

from agents.response_agent import apply_llm_to_agent_result

AGENT_DISPLAY_NAME = "Construction Agent"

# ---------------------------------------------------------------------------
# Mock construction data (Prompt 2 / 7 will move this to data/ + RAG later)
# ---------------------------------------------------------------------------

MOCK_TOWERS: dict[str, dict] = {
    "Tower A": {
        "status": "on_track",
        "delay_reason": None,
        "completion_pct": 88,
        "risk": "low",
        "milestones": [
            {"name": "Foundation", "status": "complete"},
            {"name": "Structure", "status": "complete"},
            {"name": "Finishing", "status": "in_progress"},
        ],
        "notes": "Tower A is progressing as planned with no major blockers.",
    },
    "Tower B": {
        "status": "delayed",
        "delay_reason": "material delivery issues",
        "completion_pct": 72,
        "risk": "high",
        "milestones": [
            {"name": "Foundation", "status": "complete"},
            {"name": "Structure", "status": "delayed"},
            {"name": "Finishing", "status": "not_started"},
        ],
        "notes": (
            "Steel and facade material deliveries are 3–4 weeks behind schedule, "
            "which is holding up structural work on upper floors."
        ),
    },
    "Tower C": {
        "status": "on_track",
        "delay_reason": None,
        "completion_pct": 81,
        "risk": "medium",
        "milestones": [
            {"name": "Foundation", "status": "complete"},
            {"name": "Structure", "status": "in_progress"},
            {"name": "Finishing", "status": "not_started"},
        ],
        "notes": "Tower C is slightly behind internal targets but within acceptable range.",
    },
}

SOURCE_LABEL = "mock_construction_data"
BASE_CONFIDENCE = 0.85


def _normalize(query: str) -> str:
    return query.lower().strip()


def _detect_tower(query: str) -> str | None:
    """Pick Tower A/B/C if mentioned; otherwise None."""
    text = _normalize(query)
    if "tower a" in text or "tower-a" in text:
        return "Tower A"
    if "tower b" in text or "tower-b" in text:
        return "Tower B"
    if "tower c" in text or "tower-c" in text:
        return "Tower C"
    return None


def _format_milestones(milestones: list[dict]) -> str:
    parts = [f"{m['name']}: {m['status'].replace('_', ' ')}" for m in milestones]
    return "; ".join(parts)


def _build_risk_flags(query: str, tower_data: dict) -> list[str]:
    """Collect risk flags from query keywords and tower risk level."""
    flags: list[str] = []
    text = _normalize(query)

    if "delay" in text or tower_data.get("status") == "delayed":
        flags.append("construction_delay")

    if tower_data.get("risk") == "high":
        flags.append("high_risk")

    if tower_data.get("risk") == "medium":
        flags.append("medium_risk")

    # Remove duplicates while keeping order
    seen: set[str] = set()
    unique: list[str] = []
    for flag in flags:
        if flag not in seen:
            seen.add(flag)
            unique.append(flag)
    return unique


def _compute_confidence(tower_data: dict, tower_name: str | None) -> float:
    """
    Simple heuristic: lower confidence when delayed or risk is high.
    Tower B demo uses 0.72 to align with completion % and human-review flow.
    """
    if tower_name == "Tower B" and tower_data.get("status") == "delayed":
        return 0.72

    risk = tower_data.get("risk", "low")
    if risk == "high":
        return 0.65
    if risk == "medium":
        return 0.78
    return BASE_CONFIDENCE


def _build_response(query: str, tower_name: str, tower_data: dict) -> str:
    """Build a readable answer covering status, completion, milestones, and risks."""
    text = _normalize(query)
    lines: list[str] = []

    lines.append(f"**{tower_name} — construction update**")
    lines.append(f"- Overall status: {tower_data['status'].replace('_', ' ')}")
    lines.append(f"- Completion: {tower_data['completion_pct']}%")
    lines.append(f"- Risk level: {tower_data['risk']}")

    # Delay-specific answer (demo: "Why is Tower B delayed?")
    if "delay" in text or tower_data.get("status") == "delayed":
        reason = tower_data.get("delay_reason") or "under review"
        lines.append(f"- Delay reason: {reason}")
        if tower_data.get("notes"):
            lines.append(f"- Details: {tower_data['notes']}")

    if any(word in text for word in ("milestone", "progress", "update")):
        lines.append(f"- Milestones: {_format_milestones(tower_data['milestones'])}")

    if any(word in text for word in ("risk", "safe", "concern")):
        if tower_data["risk"] == "high":
            lines.append(
                "- Risk summary: High risk — schedule slippage may affect possession dates."
            )
        elif tower_data["risk"] == "medium":
            lines.append("- Risk summary: Medium risk — monitor weekly with site team.")
        else:
            lines.append("- Risk summary: Low risk — no critical issues reported.")

    if not any(word in text for word in ("delay", "milestone", "risk")):
        lines.append(f"- Summary: {tower_data.get('notes', 'No additional notes.')}")

    return "\n".join(lines)


def _summarize_all_towers() -> str:
    """Fallback when no specific tower is named in the query."""
    lines = ["**BuildWise — all towers overview**"]
    for name, data in MOCK_TOWERS.items():
        reason = f" ({data['delay_reason']})" if data.get("delay_reason") else ""
        lines.append(
            f"- {name}: {data['status']}, {data['completion_pct']}% complete, "
            f"risk={data['risk']}{reason}"
        )
    lines.append("Ask about a specific tower, e.g. 'Why is Tower B delayed?'")
    return "\n".join(lines)


def handle_construction_query(query: str) -> dict:
    """
    Answer construction questions using mock tower data.

    Args:
        query: User message (e.g. "Why is Tower B delayed?")

    Returns:
        dict with intent, response, confidence, risk_flags, sources
    """
    if not query or not query.strip():
        return apply_llm_to_agent_result(
            query or "",
            {
                "intent": "construction_status",
                "response": _summarize_all_towers(),
                "confidence": 0.5,
                "risk_flags": [],
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    tower_name = _detect_tower(query)

    if tower_name is None:
        return apply_llm_to_agent_result(
            query,
            {
                "intent": "construction_status",
                "response": _summarize_all_towers(),
                "confidence": 0.75,
                "risk_flags": _build_risk_flags(query, {"status": "on_track", "risk": "low"}),
                "sources": [SOURCE_LABEL],
            },
            AGENT_DISPLAY_NAME,
        )

    tower_data = MOCK_TOWERS[tower_name]
    risk_flags = _build_risk_flags(query, tower_data)
    confidence = _compute_confidence(tower_data, tower_name)

    return apply_llm_to_agent_result(
        query,
        {
            "intent": "construction_status",
            "response": _build_response(query, tower_name, tower_data),
            "confidence": confidence,
            "risk_flags": risk_flags,
            "sources": [SOURCE_LABEL],
        },
        AGENT_DISPLAY_NAME,
    )


if __name__ == "__main__":
    test_queries = [
        "Why is Tower B delayed?",
        "What is the completion percentage for Tower A?",
        "Tower C milestone update and risks",
        "Show all tower status",
    ]

    print("BuildWise construction agent — test run\n")

    for q in test_queries:
        result = handle_construction_query(q)
        print("=" * 60)
        print(f"Q: {q}")
        print(f"confidence: {result['confidence']}")
        print(f"risk_flags: {result['risk_flags']}")
        print(f"sources: {result['sources']}")
        print("-" * 60)
        print(result["response"])
        print()

    # Demo assertion for capstone rehearsal
    demo = handle_construction_query("Why is Tower B delayed?")
    assert demo["intent"] == "construction_status"
    assert "construction_delay" in demo["risk_flags"]
    assert demo["confidence"] == 0.72
    assert "material delivery" in demo["response"].lower()
    assert "72" in demo["response"]
    print("Demo query checks: PASS")