"""Deterministic policy decision engine for Case Expenses (Story 1-2).

Pure, dependency-free module: no SQLite, no MCP, no LLM. Implements
`POLICY.md`'s precedence order, per-window aggregation, and duplicate
detection to decide every line item on a claim.

Public entry point: `decide_claim`.
"""

import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

_NOT_REIMBURSABLE_CLAUSES = {
    "alcohol": "3.1",
    "personal": "3.2",
    "fine": "3.3",
}

_CATEGORY_CLAUSES = {
    "meals": "2.1",
    "hotel": "2.2",
    "flight": "2.3",
    "ground": "6.1",
}

_DAY_AGGREGATED_CATEGORIES = {"meals", "ground"}

_IT_APPROVAL_CODE = re.compile(r"ITA-\d+")

_RECEIPT_LIMIT = Decimal("25")
_OVER_LIMIT_FLAG_FACTOR = Decimal("1.2")


def _limit_bucket(amount: Decimal, limit: Decimal) -> str:
    """approve / flag / reject per POLICY.md 2.4."""
    if amount <= limit:
        return "approve"
    if amount <= limit * _OVER_LIMIT_FLAG_FACTOR:
        return "flag"
    return "reject"


def decide_claim(
    line_items: list[dict],
    employee: dict,
    limits_by_city: dict[str, dict[str, Decimal]],
    submitted_at: str,
) -> dict[str, tuple[str, str]]:
    """Decide every line item on one claim, per POLICY.md's precedence order.

    Args:
        line_items: One claim's line item rows (all columns `get_claim`
            returns: line_id, claim_id, date, city, category, merchant,
            amount, has_receipt, description).
        employee: The claim's employee (kept for interface parity with
            `get_employee`'s shape; POLICY.md's limits key on the line
            item's own city, not the employee's, so this is unused here).
        limits_by_city: `city -> {category: Decimal(limit)}`, scoped to this
            claim's employee's `level` — built by the caller from one
            `get_policy_limits(employee.level, city)` call per distinct city
            among the claim's line items. Mixing levels into one
            `limits_by_city` (or omitting the level dimension) produces
            wrong decisions with no error from this function.
        submitted_at: The claim's `submitted_at` date (ISO 'YYYY-MM-DD'),
            needed for the 60-day check (clause 1.2).

    Returns:
        `{line_id: (decision, clause)}` for every line item.

    Duplicate detection (5.1) is scoped to the line items passed in — i.e.
    one claim — not every claim by this employee, even though POLICY.md's
    text says "same employee." This is an accepted, data-justified
    approximation (architecture spine AD-4): a full scan of the seed data
    found zero cross-claim duplicates for any employee.
    """
    del employee  # unused: limits key on the line item's own city, not the employee's

    ordered_items = sorted(line_items, key=lambda item: item["line_id"])

    seen_by_key: dict[tuple[str, str, Decimal], str] = {}
    duplicate_line_ids: set[str] = set()
    for item in ordered_items:
        key = (item["date"], item["merchant"], Decimal(item["amount"]))
        if key in seen_by_key:
            duplicate_line_ids.add(item["line_id"])
        else:
            seen_by_key[key] = item["line_id"]

    day_totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for item in ordered_items:
        if item["category"] in _DAY_AGGREGATED_CATEGORIES:
            day_totals[(item["date"], item["category"])] += Decimal(item["amount"])

    decisions: dict[str, tuple[str, str]] = {}
    for item in ordered_items:
        line_id = item["line_id"]
        category = item["category"]
        amount = Decimal(item["amount"])

        clause = _NOT_REIMBURSABLE_CLAUSES.get(category)
        if clause is not None:
            decisions[line_id] = ("reject", clause)
            continue

        if line_id in duplicate_line_ids:
            decisions[line_id] = ("reject", "5.1")
            continue

        if _days_between(item["date"], submitted_at) > 60:
            decisions[line_id] = ("reject", "1.2")
            continue

        if category in ("software", "equipment"):
            if _IT_APPROVAL_CODE.search(item["description"]):
                decisions[line_id] = ("approve", "4.1")
            else:
                decisions[line_id] = ("reject", "4.1")
            continue

        category_clause = _CATEGORY_CLAUSES[category]
        if category in _DAY_AGGREGATED_CATEGORIES:
            compare_amount = day_totals[(item["date"], category)]
        else:
            compare_amount = amount
        limit = limits_by_city.get(item["city"], {}).get(category)
        if limit is not None:
            bucket = _limit_bucket(compare_amount, limit)
            if bucket in ("flag", "reject"):
                decisions[line_id] = (bucket, category_clause)
                continue

        if amount > _RECEIPT_LIMIT and item["has_receipt"] == "no":
            decisions[line_id] = ("flag", "1.3")
            continue

        decisions[line_id] = ("approve", category_clause)

    return decisions


def _days_between(earlier: str, later: str) -> int:
    """Days between two ISO 'YYYY-MM-DD' date strings (later - earlier)."""
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
