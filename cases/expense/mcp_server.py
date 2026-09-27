"""MCP server that gives the expense-claim agent read access to app.db over stdio."""

import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent / "app.db"

server = FastMCP("expense", log_level="WARNING")


def _query(sql: str, *params: str) -> list[dict]:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "app.db not found. Load the data first: uv run python cases/expense/load_seed.py"
        )
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params)]


@server.tool()
def get_claim(claim_id: str) -> dict:
    """Return one expense claim by its ID (for example CL-2001): the employee_id and every line item on the claim, with all seed columns. Amounts are decimal-safe strings."""
    claims = _query("SELECT claim_id, employee_id, submitted_at, purpose FROM claims WHERE claim_id = ?", claim_id)
    if not claims:
        raise ValueError(f"No claim with ID {claim_id}")
    claim = claims[0]
    claim["line_items"] = _query(
        "SELECT line_id, claim_id, date, city, category, merchant, amount, has_receipt, description "
        "FROM line_items WHERE claim_id = ?",
        claim_id,
    )
    return claim


@server.tool()
def get_employee(employee_id: str) -> dict:
    """Return an employee's level and city by their ID (for example E-101). Needs the employee_id from get_claim."""
    rows = _query("SELECT level, city FROM employees WHERE employee_id = ?", employee_id)
    if not rows:
        raise ValueError(f"No employee with ID {employee_id}")
    return rows[0]


@server.tool()
def get_policy_limits(level: str, city: str) -> dict:
    """Return the per-category spending limits (meals, hotel, flight, ground) for an employee's level and city, as decimal-safe strings. Needs the level and city from get_employee."""
    rows = _query(
        "SELECT category, limit_cad FROM limits WHERE level = ? AND city = ?",
        level,
        city,
    )
    if not rows:
        raise ValueError(f"No policy limits for level {level} in {city}")
    return {row["category"]: row["limit_cad"] for row in rows}


if __name__ == "__main__":
    server.run()
