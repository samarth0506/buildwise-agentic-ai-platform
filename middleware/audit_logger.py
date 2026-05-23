"""
BuildWise audit logger (scaffold).

Member 2 backend — placeholder for append-only audit events to
``data/audit_logs.json`` (routing decisions, HITL actions, errors).
"""

from __future__ import annotations

from typing import Any, Dict


def log_event(event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Append an audit event to the audit log store.

    Placeholder — returns ``False`` until persistence is implemented.
    """
    _ = (event_type, payload)
    return False
