"""One-off Member 2 backend integration audit (run from project root)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agents  # noqa: F401
import middleware  # noqa: F401
import rag  # noqa: F401

from middleware.audit_logger import get_audit_summary, load_audit_logs, save_audit_logs
from middleware.hitl_service import get_pending_reviews, load_review_queue, save_review_queue
from middleware.router import handle_user_query
from middleware.ticket_service import get_open_tickets, load_tickets, save_tickets

QUERIES = [
    "Why is Tower B delayed?",
    "Water leakage in apartment 1203.",
    "I am angry about my payment dispute.",
    "Show me 2BHK under 90 lakhs in Bangalore.",
    "What documents are pending for registration?",
]

EXPECTED = {
    QUERIES[0]: {"intent": "construction_status", "status": "pending_review", "review": True},
    QUERIES[1]: {"intent": "maintenance_issue", "ticket": True},
    QUERIES[2]: {"intent": "escalation", "status": "pending_review", "review": True, "ticket": True},
    QUERIES[3]: {"intent": "property_inquiry", "status": "completed"},
    QUERIES[4]: {"intent": "documentation_support"},
}


def main() -> None:
    save_review_queue([])
    save_tickets([])
    save_audit_logs([])

    results = []
    for q in QUERIES:
        r = handle_user_query(q)
        results.append(r)
        print(
            f"OK | {q[:45]:45} | intent={r['intent']:22} | status={r['status']:15} | "
            f"review={str(r['review_id'])[:12]:12} | ticket={str(r['ticket_id'])[:12]:12} | "
            f"audit={str(r['audit_log_id'])[:12]}"
        )

    rq = load_review_queue()
    tk = load_tickets()
    al = load_audit_logs()
    print("\n--- JSON stores ---")
    print(f"review_queue: {len(rq)} total, {len(get_pending_reviews())} pending")
    print(f"tickets:      {len(tk)} total, {len(get_open_tickets())} open")
    print(f"audit_logs:   {len(al)} total")
    print(f"summary:      {json.dumps(get_audit_summary())}")

    # Assertions
    for q, exp in EXPECTED.items():
        r = next(x for x in results if x["query"] == q)
        assert r["intent"] == exp["intent"], f"{q}: intent {r['intent']} != {exp['intent']}"
        if "status" in exp:
            assert r["status"] == exp["status"], f"{q}: status {r['status']}"
        if exp.get("review"):
            assert r["review_id"], f"{q}: missing review_id"
        if exp.get("ticket"):
            assert r["ticket_id"], f"{q}: missing ticket_id"
        assert r["audit_log_id"], f"{q}: missing audit_log_id"

    assert len(al) == 5
    assert len(rq) >= 3  # review-required queries
    assert len(tk) >= 2

    # Member 3 import path
    from middleware.router import handle_user_query as m3  # noqa: F401

    print("\nAll integration audit checks: PASS")


if __name__ == "__main__":
    main()
