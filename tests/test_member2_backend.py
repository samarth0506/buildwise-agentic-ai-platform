"""
Smoke tests for Member 2 backend scaffold.

Verifies packages import and placeholder modules expose expected entry points.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def test_packages_import() -> None:
    import agents  # noqa: F401
    import middleware  # noqa: F401
    import rag  # noqa: F401


def test_middleware_exports() -> None:
    from middleware import handle_user_query

    result = handle_user_query("test query")
    assert isinstance(result, dict)
    assert "final_response" in result


def test_json_scaffolds_are_empty_lists() -> None:
    for name in ("review_queue.json", "tickets.json", "audit_logs.json"):
        path = DATA_DIR / name
        assert path.is_file(), f"Missing {name}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == [], f"{name} should initialize to []"
