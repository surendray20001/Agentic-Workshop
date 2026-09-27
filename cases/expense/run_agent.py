"""Orchestrate a full decision run over all of Case Expenses' claims (Story 1-4).

Deterministic driver: no LLM, no LangChain, no MLflow tracing -- those are
Epic 2's concern (CAP-7, explanation + eval). This script truncates
`decisions`, then for every claim assembles context via the MCP tools,
decides via `decision_engine.decide_claim`, and records every line item's
decision.
"""

import csv
from decimal import Decimal
from pathlib import Path

import decision_engine
import mcp_server

CASE_DIR = Path(__file__).resolve().parent
CLAIMS_CSV = CASE_DIR / "seed" / "claims.csv"


def _claim_ids() -> list[str]:
    with CLAIMS_CSV.open(newline="", encoding="utf-8") as f:
        return [row["claim_id"] for row in csv.DictReader(f)]


def _limits_by_city(level: str, cities: set[str]) -> dict[str, dict[str, Decimal]]:
    limits_by_city: dict[str, dict[str, Decimal]] = {}
    for city in cities:
        raw_limits = mcp_server.get_policy_limits(level, city)
        limits_by_city[city] = {category: Decimal(limit) for category, limit in raw_limits.items()}
    return limits_by_city


def run() -> int:
    """Run the full pipeline. Returns the number of line-item decisions recorded."""
    mcp_server.truncate_decisions()

    recorded = 0
    for claim_id in _claim_ids():
        claim = mcp_server.get_claim(claim_id)
        employee = mcp_server.get_employee(claim["employee_id"])
        line_items = claim["line_items"]

        cities = {item["city"] for item in line_items}
        limits_by_city = _limits_by_city(employee["level"], cities)

        decisions = decision_engine.decide_claim(
            line_items, employee, limits_by_city, claim["submitted_at"]
        )
        for line_id, (decision, clause) in decisions.items():
            mcp_server.record_decision(line_id, decision, clause)
            recorded += 1

    return recorded


if __name__ == "__main__":
    total = run()
    print(f"Recorded {total} line-item decisions across all claims.")
