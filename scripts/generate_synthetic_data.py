"""
BuildWise synthetic data generator.

Generates realistic CSV and FAQ datasets for the BuildWise Agentic AI
Bangalore real-estate + construction platform. Writes outputs under ``data/``
and resets runtime JSON stores to empty lists.

Run from project root::

    python scripts/generate_synthetic_data.py
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_ROWS = 200
RANDOM_SEED = 42

PROJECT_NAMES = (
    "BuildWise Greens",
    "BuildWise Heights",
    "BuildWise Skyline",
    "BuildWise Urbania",
    "BuildWise Lakeview",
    "BuildWise Meridian",
)

TOWERS = ("Tower A", "Tower B", "Tower C", "Tower D", "Tower E", "Tower F")

BHK_TYPES = ("1BHK", "2BHK", "3BHK", "4BHK")

LOCATIONS = (
    "Whitefield",
    "Electronic City",
    "Sarjapur",
    "Hebbal",
    "Indiranagar",
    "HSR Layout",
)

AVAILABILITY_STATUSES = ("available", "limited", "sold_out", "waitlist", "blocked")

CONSTRUCTION_STATUSES = ("on_track", "delayed", "ahead_of_schedule", "on_hold")
RISK_LEVELS = ("low", "medium", "high")
CONTRACTORS = (
    "L&T Construction",
    "Shapoorji Pallonji",
    "Prestige Constructions",
    "Brigade Builders",
    "Sobha Developers",
    "Puravankara Projects",
)

DELAY_REASONS = (
    "material delivery issues",
    "labour shortage",
    "monsoon impact",
    "regulatory approval pending",
    "equipment breakdown",
    "design revision",
    "none",
)

MAINTENANCE_ISSUE_TYPES = (
    "water leakage",
    "electricity",
    "plumbing",
    "elevator malfunction",
    "AC issue",
    "parking access",
    "fire safety check",
    "common area cleaning",
)

SEVERITIES = ("low", "medium", "high", "critical")
MAINTENANCE_STATUSES = ("open", "in_progress", "resolved", "closed", "escalated")
MAINTENANCE_TEAMS = (
    "Plumbing & Sanitary",
    "Electrical Maintenance",
    "HVAC Services",
    "Elevator & Lifts",
    "Facilities Management",
    "Customer Support",
)

DOCUMENT_TYPES = (
    "KYC",
    "registration",
    "loan approval",
    "payment receipt",
    "occupancy certificate",
    "sale agreement",
    "NOC",
    "handover checklist",
)

DOC_STATUSES = ("open", "in_review", "pending_customer", "resolved", "closed")
DOC_OFFICERS = (
    "Priya Sharma",
    "Rahul Menon",
    "Ananya Iyer",
    "Vikram Desai",
    "Sneha Reddy",
    "Arjun Nair",
)

FIRST_NAMES = (
    "Aarav", "Diya", "Karan", "Meera", "Rohan", "Sanya", "Aditya", "Neha",
    "Vivek", "Pooja", "Sanjay", "Lakshmi", "Nikhil", "Anjali", "Harish",
)
LAST_NAMES = (
    "Kumar", "Reddy", "Iyer", "Menon", "Sharma", "Patel", "Nair", "Rao",
    "Gupta", "Das", "Joseph", "Fernandes", "Choudhury", "Banerjee",
)

JSON_STORES = ("tickets.json", "audit_logs.json", "review_queue.json")

# Guaranteed demo row for capstone / RAG queries ("Why is Tower B delayed?")
TOWER_B_DEMO_ROW: Dict[str, Any] = {
    "tower": "Tower B",
    "phase": "Phase 2",
    "completion_percent": 72,
    "status": "delayed",
    "delay_days": 14,
    "delay_reason": "material delivery issues",
    "risk_level": "high",
    "contractor": "L&T Construction",
    "expected_completion": "2026-09-30",
    "last_updated": date.today().isoformat(),
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Return repository root (parent of ``scripts/``)."""
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """Return ``data/`` path, creating it if missing."""
    data_dir = get_project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def write_csv(df: pd.DataFrame, filename: str) -> Path:
    """Write a DataFrame to ``data/<filename>`` as UTF-8 CSV."""
    path = get_data_dir() / filename
    df.to_csv(path, index=False, encoding="utf-8")
    logger.info("Wrote %d rows to %s", len(df), path)
    return path


def write_json_empty(filename: str) -> Path:
    """Reset a JSON store to an empty list ``[]``."""
    path = get_data_dir() / filename
    path.write_text("[]\n", encoding="utf-8")
    logger.info("Reset %s to empty list", path)
    return path


def write_text(filename: str, content: str) -> Path:
    """Write plain text to ``data/<filename>``."""
    path = get_data_dir() / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    logger.info("Wrote FAQ text to %s (%d chars)", path, len(content))
    return path


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------


def _random_date(start: date, end: date) -> date:
    """Pick a random date between *start* and *end* (inclusive)."""
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


def _random_customer_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _bhk_square_feet(bhk: str) -> int:
    """Return a plausible carpet area for the given BHK type."""
    ranges = {
        "1BHK": (550, 750),
        "2BHK": (900, 1200),
        "3BHK": (1250, 1650),
        "4BHK": (1700, 2400),
    }
    low, high = ranges[bhk]
    return random.randrange(low, high + 1, 10)


def _price_for_bhk(bhk: str, location: str) -> float:
    """Estimate price in lakhs based on unit size and micro-market."""
    base = {"1BHK": 45, "2BHK": 72, "3BHK": 105, "4BHK": 155}[bhk]
    premium = {
        "Indiranagar": 1.25,
        "HSR Layout": 1.20,
        "Whitefield": 1.10,
        "Hebbal": 1.05,
        "Sarjapur": 1.00,
        "Electronic City": 0.95,
    }[location]
    jitter = random.uniform(-8, 12)
    return round(base * premium + jitter, 1)


def generate_property_rows(count: int = TARGET_ROWS) -> List[Dict[str, Any]]:
    """Build property listing records."""
    rows: List[Dict[str, Any]] = []
    today = date.today()

    for _ in range(count):
        bhk = random.choice(BHK_TYPES)
        location = random.choice(LOCATIONS)
        tower = random.choice(TOWERS)
        project = random.choice(PROJECT_NAMES)
        sqft = _bhk_square_feet(bhk)
        possession = _random_date(today + timedelta(days=120), today + timedelta(days=900))

        rows.append(
            {
                "project_name": project,
                "tower": tower,
                "unit_id": f"BW-{uuid.uuid4().hex[:8].upper()}",
                "bhk_type": bhk,
                "square_feet": sqft,
                "price_lakhs": _price_for_bhk(bhk, location),
                "location": f"Bangalore — {location}",
                "availability_status": random.choice(AVAILABILITY_STATUSES),
                "possession_date": possession.isoformat(),
            }
        )

    return rows


def _construction_row(tower: str, *, force_demo: bool = False) -> Dict[str, Any]:
    """Build one construction status record."""
    if force_demo:
        return dict(TOWER_B_DEMO_ROW)

    status = random.choices(
        CONSTRUCTION_STATUSES,
        weights=[55, 20, 15, 10],
        k=1,
    )[0]
    completion = random.randint(35, 98)
    delay_days = 0
    delay_reason = "none"
    risk = random.choice(RISK_LEVELS)

    if status == "delayed":
        delay_days = random.randint(3, 45)
        delay_reason = random.choice(DELAY_REASONS[:-1])  # exclude "none"
        risk = random.choices(RISK_LEVELS, weights=[10, 30, 60], k=1)[0]
        completion = min(completion, random.randint(55, 85))
    elif status == "on_hold":
        delay_days = random.randint(10, 60)
        delay_reason = random.choice(DELAY_REASONS[:-1])
        risk = "high"

    phase_num = random.randint(1, 4)
    expected = _random_date(date.today() + timedelta(days=90), date.today() + timedelta(days=720))

    return {
        "tower": tower,
        "phase": f"Phase {phase_num}",
        "completion_percent": completion,
        "status": status,
        "delay_days": delay_days,
        "delay_reason": delay_reason,
        "risk_level": risk,
        "contractor": random.choice(CONTRACTORS),
        "expected_completion": expected.isoformat(),
        "last_updated": _random_date(date.today() - timedelta(days=30), date.today()).isoformat(),
    }


def generate_construction_rows(count: int = TARGET_ROWS) -> List[Dict[str, Any]]:
    """Build construction update records with a guaranteed Tower B demo row."""
    rows: List[Dict[str, Any]] = []

    # First row: capstone demo anchor
    rows.append(_construction_row("Tower B", force_demo=True))

    for _ in range(count - 1):
        rows.append(_construction_row(random.choice(TOWERS)))

    return rows


def generate_maintenance_rows(count: int = TARGET_ROWS) -> List[Dict[str, Any]]:
    """Build resident maintenance issue records."""
    rows: List[Dict[str, Any]] = []
    today = date.today()

    for _ in range(count):
        tower = random.choice(TOWERS)
        floor = random.randint(1, 22)
        unit = random.randint(1, 8)
        reported = _random_date(today - timedelta(days=60), today)
        status = random.choice(MAINTENANCE_STATUSES)
        eta_days = random.randint(1, 21) if status in ("open", "in_progress", "escalated") else 0
        resolution_eta = (reported + timedelta(days=eta_days)).isoformat() if eta_days else ""

        rows.append(
            {
                "apartment_id": f"{tower.replace(' ', '-')}-F{floor}U{unit}",
                "issue_type": random.choice(MAINTENANCE_ISSUE_TYPES),
                "severity": random.choices(SEVERITIES, weights=[30, 40, 22, 8], k=1)[0],
                "status": status,
                "assigned_team": random.choice(MAINTENANCE_TEAMS),
                "reported_date": reported.isoformat(),
                "resolution_eta": resolution_eta,
            }
        )

    return rows


def generate_documentation_rows(count: int = TARGET_ROWS) -> List[Dict[str, Any]]:
    """Build documentation / paperwork case records."""
    rows: List[Dict[str, Any]] = []
    today = date.today()

    pending_pool = (
        "PAN copy",
        "Aadhaar",
        "address proof",
        "bank sanction letter",
        "sale deed draft",
        "payment receipt",
        "NOC from builder",
        "occupancy certificate copy",
        "passport photo",
        "loan disbursement schedule",
    )

    for _ in range(count):
        doc_type = random.choice(DOCUMENT_TYPES)
        status = random.choice(DOC_STATUSES)
        deadline = _random_date(today, today + timedelta(days=45))
        num_pending = random.randint(0, 3) if status != "resolved" else 0
        pending = ", ".join(random.sample(pending_pool, k=num_pending)) if num_pending else "none"

        rows.append(
            {
                "case_id": f"DOC-{uuid.uuid4().hex[:6].upper()}",
                "customer_name": _random_customer_name(),
                "document_type": doc_type,
                "status": status,
                "pending_documents": pending,
                "assigned_officer": random.choice(DOC_OFFICERS),
                "submission_deadline": deadline.isoformat(),
            }
        )

    return rows


def generate_faq_text() -> str:
    """Return realistic FAQ paragraphs for ``documentation_faq.txt``."""
    return """
Why is Tower B delayed?

Tower B is currently delayed due to material delivery issues. Steel and facade material deliveries are running about 14 days behind schedule, which affects structural work on upper floors. Current completion is around 72% with high schedule risk. The project team is expediting supplier shipments and adjusting the critical path schedule.

How do I complete KYC for my BuildWise unit?

Submit a government photo ID (Aadhaar or passport), PAN card, address proof, and passport-size photographs through the BuildWise customer portal or at the sales office. Verification typically completes within 2-3 business days. You will receive email confirmation once KYC is approved.

What documents are required for property registration in Bangalore?

After booking, review the draft sale agreement, pay applicable stamp duty and registration charges, and schedule an appointment at the sub-registrar office. Required documents usually include KYC proofs, booking acknowledgment, payment receipts, and builder NOC. Registration timelines vary by case but often take 2-4 weeks after milestones are met.

How does the BuildWise payment schedule work?

Payments follow construction-linked milestones: booking amount, agreement signing, foundation, structure, finishing, and possession. Receipts are issued within 2 business days of payment posting. Keep receipts for home loan disbursement and tax records.

When will possession be handed over?

Possession dates depend on tower completion, snag-list sign-off, and final payment clearance. For delayed towers such as Tower B, revised timelines are shared after site verification. Contact handover@buildwise.example for unit-specific schedules.

How can buyers get construction updates?

Buyers can ask about tower status, completion percentage, delay reasons, and milestone progress through the BuildWise chatbot. For legal, refund, or payment disputes, contact the customer relations desk for escalation.

What maintenance support is available after handover?

Report issues such as water leakage, plumbing, electrical faults, elevator problems, or AC servicing through the resident portal. Urgent safety issues are triaged within 24 hours. Warranty defects are reviewed against your handover checklist within 5 business days.

How do I obtain an occupancy certificate (OC)?

The occupancy certificate is issued by the local authority after statutory approvals and final inspections. BuildWise shares OC copies at handover once the tower receives clearance. Track your documentation case status with your assigned officer.
""".strip()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def tower_b_demo_exists(df: pd.DataFrame) -> bool:
    """Return True if construction data contains the Tower B delay demo pattern."""
    if df.empty:
        return False

    mask = (
        (df["tower"] == "Tower B")
        & (df["status"] == "delayed")
        & (df["delay_reason"].str.contains("material delivery", case=False, na=False))
        & (df["completion_percent"] == 72)
        & (df["delay_days"] == 14)
        & (df["risk_level"] == "high")
    )
    return bool(mask.any())


def validate_json_empty(path: Path) -> bool:
    """Return True if *path* contains a JSON empty list."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data == []
    except (json.JSONDecodeError, OSError):
        return False


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def generate_all() -> Dict[str, Path]:
    """
    Generate every dataset and reset JSON stores.

    Returns:
        Mapping of logical name → written file path.
    """
    random.seed(RANDOM_SEED)

    outputs: Dict[str, Path] = {}

    property_df = pd.DataFrame(generate_property_rows(TARGET_ROWS))
    outputs["property_data"] = write_csv(property_df, "property_data.csv")

    construction_df = pd.DataFrame(generate_construction_rows(TARGET_ROWS))
    outputs["construction_status"] = write_csv(construction_df, "construction_status.csv")

    maintenance_df = pd.DataFrame(generate_maintenance_rows(TARGET_ROWS))
    outputs["maintenance_issues"] = write_csv(maintenance_df, "maintenance_issues.csv")

    documentation_df = pd.DataFrame(generate_documentation_rows(TARGET_ROWS))
    outputs["documentation_cases"] = write_csv(documentation_df, "documentation_cases.csv")

    outputs["documentation_faq"] = write_text("documentation_faq.txt", generate_faq_text())

    for name in JSON_STORES:
        outputs[name.replace(".json", "")] = write_json_empty(name)

    return outputs


def main() -> None:
    """Run full generation and print a summary report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 70)
    print("BuildWise — synthetic data generation")
    print(f"Seed: {RANDOM_SEED}  |  Target rows per CSV: {TARGET_ROWS}")
    print("=" * 70)

    outputs = generate_all()

    print("\n--- Row counts ---")
    for key in ("property_data", "construction_status", "maintenance_issues", "documentation_cases"):
        path = outputs[key]
        df = pd.read_csv(path, encoding="utf-8")
        print(f"  {path.name}: {len(df)} rows")

    construction_df = pd.read_csv(outputs["construction_status"], encoding="utf-8")
    demo_ok = tower_b_demo_exists(construction_df)
    print(f"\n--- Tower B demo row ---")
    print(f"  Present: {'YES' if demo_ok else 'NO'}")
    if demo_ok:
        demo = construction_df.loc[
            (construction_df["tower"] == "Tower B")
            & (construction_df["status"] == "delayed")
            & (construction_df["completion_percent"] == 72)
        ].iloc[0]
        print(
            f"  Sample: tower={demo['tower']}, completion={demo['completion_percent']}%, "
            f"delay_days={demo['delay_days']}, risk={demo['risk_level']}, "
            f"reason={demo['delay_reason']}"
        )

    print("\n--- JSON stores ---")
    for name in JSON_STORES:
        path = outputs[name.replace(".json", "")]
        valid = validate_json_empty(path)
        print(f"  {path.name}: {'valid []' if valid else 'INVALID'}")

    print("\n--- Generated files ---")
    for label, path in outputs.items():
        print(f"  {label}: {path}")

    if not demo_ok:
        raise SystemExit("Validation failed: Tower B demo row not found in construction_status.csv")

    print("\nGeneration complete.")


if __name__ == "__main__":
    main()
