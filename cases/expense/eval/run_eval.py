"""Score the current `decisions` table against eval/labelled.csv (Story 2-2, CAP-8).

Three checks, per BRIEF.md: decision match per line item, clause match per
line item, and reimbursable-total match per claim, across the labelled
claims. The reimbursable total is the Decimal sum of every `approve`-decided
line item's amount, grouped by claim -- including items still pending the
$500 gate (Spine AD-10).

Scores whatever is in `decisions` now; it never runs the agent or writes
anything. A partial run is not eval-safe (Spine AD-12), so it refuses to
score unless `decisions` covers every line item.

Exit codes: 0 every check passed, 1 a check failed, 2 cannot score.
"""

import csv
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
CASE_DIR = EVAL_DIR.parent
DB_PATH = CASE_DIR / "app.db"
LABELS_CSV = EVAL_DIR / "labelled.csv"


class NotEvalReady(Exception):
    """`decisions` isn't a complete run, so scoring it would be meaningless."""


@dataclass
class Check:
    name: str
    total: int
    mismatches: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return self.total - len(self.mismatches)

    @property
    def ok(self) -> bool:
        return not self.mismatches


def _read_labels() -> list[dict]:
    with LABELS_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_db() -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, Decimal]]]:
    """Returns (decisions by line_id, (claim_id, amount) by line_id)."""
    if not DB_PATH.exists():
        raise NotEvalReady(f"{DB_PATH} not found -- load the seed and run the agent first.")
    # Read-only: the eval must never create or modify app.db.
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        try:
            decisions = {
                line_id: (decision, clause)
                for line_id, decision, clause in conn.execute(
                    "SELECT line_id, decision, clause FROM decisions"
                )
            }
        except sqlite3.OperationalError as exc:
            raise NotEvalReady(f"no decisions table ({exc}) -- run the agent first.") from exc
        line_items = {
            line_id: (claim_id, Decimal(amount))
            for line_id, claim_id, amount in conn.execute(
                "SELECT line_id, claim_id, amount FROM line_items"
            )
        }
    missing = sorted(set(line_items) - set(decisions))
    if missing:
        raise NotEvalReady(
            f"decisions covers {len(line_items) - len(missing)} of {len(line_items)} line items "
            f"(missing e.g. {', '.join(missing[:5])}) -- a partial run is not eval-safe; "
            "re-run the agent over all claims first."
        )
    return decisions, line_items


def _reimbursable_totals(
    decision_by_line: dict[str, str], line_items: dict[str, tuple[str, Decimal]]
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line_id, decision in decision_by_line.items():
        claim_id, amount = line_items[line_id]
        totals[claim_id] += amount if decision == "approve" else Decimal("0")
    return totals


def evaluate() -> list[Check]:
    labels = _read_labels()
    decisions, line_items = _read_db()

    decision_check = Check("decision match (per line item)", len(labels))
    clause_check = Check("clause match (per line item)", len(labels))
    for label in labels:
        line_id = label["line_id"]
        actual_decision, actual_clause = decisions[line_id]
        if actual_decision != label["expected_decision"]:
            decision_check.mismatches.append(
                f"{line_id}: expected {label['expected_decision']}, got {actual_decision}"
            )
        if actual_clause != label["expected_clause"]:
            clause_check.mismatches.append(
                f"{line_id}: expected {label['expected_clause']}, got {actual_clause}"
            )

    labelled_lines = [label["line_id"] for label in labels]
    expected_totals = _reimbursable_totals(
        {label["line_id"]: label["expected_decision"] for label in labels}, line_items
    )
    actual_totals = _reimbursable_totals(
        {line_id: decisions[line_id][0] for line_id in labelled_lines}, line_items
    )
    claim_ids = sorted({label["claim_id"] for label in labels})
    total_check = Check("reimbursable total match (per claim)", len(claim_ids))
    for claim_id in claim_ids:
        if actual_totals[claim_id] != expected_totals[claim_id]:
            total_check.mismatches.append(
                f"{claim_id}: expected {expected_totals[claim_id]}, got {actual_totals[claim_id]}"
            )

    return [decision_check, clause_check, total_check]


def main() -> int:
    try:
        checks = evaluate()
    except NotEvalReady as exc:
        print(f"Cannot score: {exc}", file=sys.stderr)
        return 2

    for check in checks:
        print(f"{'PASS' if check.ok else 'FAIL'}  {check.name}: {check.passed}/{check.total}")
        for mismatch in check.mismatches:
            print(f"      {mismatch}")
    all_ok = all(check.ok for check in checks)
    print("All checks passed." if all_ok else "Some checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
