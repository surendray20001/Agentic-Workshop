"""Tests for Case Expenses' deterministic decision engine (Story 1-2).

Covers the I/O & Edge-Case Matrix in
_bmad-output/specs/spec-epic-1/stories/1-2-deterministic-policy-decision-engine.md.
"""

import csv
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
SEED_DIR = CASE_DIR / "seed"
EVAL_DIR = CASE_DIR / "eval"

sys.path.insert(0, str(CASE_DIR))

import decision_engine  # noqa: E402


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _build_limits_by_city_for_level(level: str) -> dict[str, dict[str, Decimal]]:
    """limits_by_city is scoped to one employee's level, as get_policy_limits(level, city) would be."""
    limits_by_city: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in _read_csv(SEED_DIR / "limits.csv"):
        if row["level"] == level:
            limits_by_city[row["city"]][row["category"]] = Decimal(row["limit_cad"])
    return limits_by_city


def test_full_labelled_set_replay():
    """Every labelled line item, across all 30 labelled claims, must match exactly."""
    claims = {r["claim_id"]: r for r in _read_csv(SEED_DIR / "claims.csv")}
    employees = {r["employee_id"]: r for r in _read_csv(SEED_DIR / "employees.csv")}
    all_items = _read_csv(SEED_DIR / "line_items.csv")
    labels = {r["line_id"]: r for r in _read_csv(EVAL_DIR / "labelled.csv")}

    by_claim: dict[str, list[dict]] = defaultdict(list)
    for item in all_items:
        by_claim[item["claim_id"]].append(item)

    checked = 0
    mismatches = []
    for claim_id, claim in claims.items():
        line_items = by_claim[claim_id]
        if not any(item["line_id"] in labels for item in line_items):
            continue  # holdout claim, no labels to check
        employee = employees[claim["employee_id"]]
        limits_by_city = _build_limits_by_city_for_level(employee["level"])
        decisions = decision_engine.decide_claim(
            line_items, employee, limits_by_city, claim["submitted_at"]
        )
        for line_id, (decision, clause) in decisions.items():
            label = labels.get(line_id)
            if label is None:
                continue
            checked += 1
            if decision != label["expected_decision"] or clause != label["expected_clause"]:
                mismatches.append(
                    (line_id, decision, clause, label["expected_decision"], label["expected_clause"])
                )

    assert checked == 119, f"expected 119 labelled line items checked, got {checked}"
    assert mismatches == [], f"{len(mismatches)} mismatches: {mismatches[:10]}"


def _decide_one(line_items, submitted_at="2026-08-15", limits_by_city=None):
    limits_by_city = limits_by_city or {}
    return decision_engine.decide_claim(line_items, {"level": "L2"}, limits_by_city, submitted_at)


def test_meals_under_limit_with_receipt_approves():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "40.00",
            "has_receipt": "yes", "description": "Lunch",
        }
    ]
    limits = {"Toronto": {"meals": Decimal("60")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-1"] == ("approve", "2.1")


def test_meals_under_limit_missing_receipt_over_25_flags_1_3():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "40.00",
            "has_receipt": "no", "description": "Lunch",
        }
    ]
    limits = {"Toronto": {"meals": Decimal("60")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-1"] == ("flag", "1.3")


def test_hotel_over_limit_by_20_percent_or_less_flags():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "hotel", "merchant": "Hotel Co", "amount": "216.00",  # 1.2x of 180
            "has_receipt": "yes", "description": "One night",
        }
    ]
    limits = {"Toronto": {"hotel": Decimal("180")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-1"] == ("flag", "2.2")


def test_hotel_over_limit_by_more_than_20_percent_rejects():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "hotel", "merchant": "Hotel Co", "amount": "220.00",  # >1.2x of 180
            "has_receipt": "yes", "description": "One night",
        }
    ]
    limits = {"Toronto": {"hotel": Decimal("180")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-1"] == ("reject", "2.2")


def test_duplicate_same_date_ties_on_line_id():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "30.00",
            "has_receipt": "yes", "description": "Lunch",
        },
        {
            "line_id": "L-2", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "30.00",
            "has_receipt": "yes", "description": "Lunch again",
        },
    ]
    limits = {"Toronto": {"meals": Decimal("60")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-2"] == ("reject", "5.1")
    assert decisions["L-1"][0] != "reject" or decisions["L-1"][1] != "5.1"


def test_duplicate_with_differently_formatted_equal_amount_still_rejects():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "40.0",
            "has_receipt": "yes", "description": "Lunch",
        },
        {
            "line_id": "L-2", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "meals", "merchant": "Cafe", "amount": "40.00",
            "has_receipt": "yes", "description": "Lunch again",
        },
    ]
    limits = {"Toronto": {"meals": Decimal("60")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-2"] == ("reject", "5.1")


def test_software_with_it_approval_code_approves():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "software", "merchant": "Figma", "amount": "144.00",
            "has_receipt": "yes", "description": "Annual licence, IT approval ITA-4471",
        }
    ]
    decisions = _decide_one(items)
    assert decisions["L-1"] == ("approve", "4.1")


def test_software_without_it_approval_code_rejects():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
            "category": "software", "merchant": "Figma", "amount": "144.00",
            "has_receipt": "yes", "description": "Annual licence",
        }
    ]
    decisions = _decide_one(items)
    assert decisions["L-1"] == ("reject", "4.1")


def test_line_item_older_than_60_days_rejects_1_2_even_over_limit():
    items = [
        {
            "line_id": "L-1", "claim_id": "CL-X", "date": "2026-05-01", "city": "Toronto",
            "category": "hotel", "merchant": "Hotel Co", "amount": "999.00",
            "has_receipt": "yes", "description": "Old stay",
        }
    ]
    limits = {"Toronto": {"hotel": Decimal("180")}}
    decisions = _decide_one(items, submitted_at="2026-08-15", limits_by_city=limits)
    assert decisions["L-1"] == ("reject", "1.2")


def test_alcohol_personal_fine_reject_regardless_of_everything_else():
    items = [
        {"line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
         "category": "alcohol", "merchant": "Wine Bar", "amount": "10.00",
         "has_receipt": "yes", "description": "Wine"},
        {"line_id": "L-2", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
         "category": "personal", "merchant": "Gym", "amount": "10.00",
         "has_receipt": "yes", "description": "Gym pass"},
        {"line_id": "L-3", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
         "category": "fine", "merchant": "City", "amount": "10.00",
         "has_receipt": "yes", "description": "Parking ticket"},
    ]
    decisions = _decide_one(items)
    assert decisions["L-1"] == ("reject", "3.1")
    assert decisions["L-2"] == ("reject", "3.2")
    assert decisions["L-3"] == ("reject", "3.3")


def test_multi_city_claim_uses_each_lines_own_city_for_limits():
    items = [
        {"line_id": "L-1", "claim_id": "CL-X", "date": "2026-08-01", "city": "Toronto",
         "category": "hotel", "merchant": "Hotel Co", "amount": "170.00",
         "has_receipt": "yes", "description": "Night in Toronto"},
        {"line_id": "L-2", "claim_id": "CL-X", "date": "2026-08-02", "city": "Montreal",
         "category": "hotel", "merchant": "Hotel Co", "amount": "170.00",
         "has_receipt": "yes", "description": "Night in Montreal"},
    ]
    limits = {"Toronto": {"hotel": Decimal("180")}, "Montreal": {"hotel": Decimal("150")}}
    decisions = _decide_one(items, limits_by_city=limits)
    assert decisions["L-1"] == ("approve", "2.2")  # 170 <= 180
    assert decisions["L-2"] == ("flag", "2.2")  # 170 > 150, <= 180 (1.2x)
