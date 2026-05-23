"""
BuildWise risk rules (scaffold).

Member 2 backend — placeholder for centralized risk classification helpers
used by the router and human-in-the-loop (HITL) pipeline.

Will map agent ``risk_flags`` and confidence scores to risk levels
(High / Medium / Low) and review triggers.
"""

from __future__ import annotations

from typing import List


def derive_risk_level(risk_flags: List[str], confidence: float) -> str:
    """
    Derive a display risk level from flags and confidence.

    Placeholder — returns ``Low`` until rules are implemented.
    """
    _ = (risk_flags, confidence)
    return "Low"
