"""Unit tests for Case Expenses' MCP claim-context tools (Story 1-1).

Covers the I/O & Edge-Case Matrix in
_bmad-output/specs/spec-epic-1/stories/1-1-mcp-server-claim-context-tools.md.
"""

import csv
import importlib
import sys
from pathlib import Path

import pytest

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
SEED_DIR = CASE_DIR / "seed"

sys.path.insert(0, str(CASE_DIR))


@pytest.fixture()
def loaded_db(tmp_path, monkeypatch):
    """Load the real seed data into a throwaway app.db for each test."""
    db_path = tmp_path / "app.db"

    import load_seed
    import mcp_server

    monkeypatch.setattr(load_seed, "DB_PATH", db_path)
    monkeypatch.setattr(mcp_server, "DB_PATH", db_path)

    load_seed.load_seed()

    return db_path


def _read_csv(name: str) -> list[dict]:
    with (SEED_DIR / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_load_seed_creates_tables_with_expected_row_counts(loaded_db):
    import sqlite3

    with sqlite3.connect(loaded_db) as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("claims", "employees", "limits", "line_items")
        }

    assert counts == {"claims": 40, "employees": 12, "limits": 80, "line_items": 159}


def test_load_seed_is_idempotent(loaded_db):
    import sqlite3

    import load_seed

    def snapshot():
        with sqlite3.connect(loaded_db) as conn:
            conn.row_factory = sqlite3.Row
            return {
                table: [
                    dict(row)
                    for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")
                ]
                for table in ("claims", "employees", "limits", "line_items")
            }

    first = snapshot()
    load_seed.load_seed()
    second = snapshot()

    assert first == second


def test_get_claim_happy_path(loaded_db):
    import mcp_server

    claim = mcp_server.get_claim("CL-2001")

    assert claim["employee_id"] == "E-101"

    expected_claim = next(
        row for row in _read_csv("claims.csv") if row["claim_id"] == "CL-2001"
    )
    assert claim["submitted_at"] == expected_claim["submitted_at"]
    assert claim["purpose"] == expected_claim["purpose"]

    expected_line_items = [
        row for row in _read_csv("line_items.csv") if row["claim_id"] == "CL-2001"
    ]
    assert len(claim["line_items"]) == len(expected_line_items)

    actual_by_id = {li["line_id"]: li for li in claim["line_items"]}
    for expected in expected_line_items:
        actual = actual_by_id[expected["line_id"]]
        for key, value in expected.items():
            assert actual[key] == value
        # amount must be a decimal-safe string, never a native float
        assert isinstance(actual["amount"], str)


def test_get_claim_not_found_raises_value_error(loaded_db):
    import mcp_server

    with pytest.raises(ValueError):
        mcp_server.get_claim("CL-9999")


def test_get_employee_happy_path(loaded_db):
    import mcp_server

    employee = mcp_server.get_employee("E-101")

    assert employee["level"] == "L2"
    assert employee["city"] == "Toronto"


def test_get_employee_not_found_raises_value_error(loaded_db):
    import mcp_server

    with pytest.raises(ValueError):
        mcp_server.get_employee("E-999")


def test_get_policy_limits_happy_path(loaded_db):
    import mcp_server

    limits = mcp_server.get_policy_limits("L2", "Toronto")

    expected = {
        row["category"]: row["limit_cad"]
        for row in _read_csv("limits.csv")
        if row["level"] == "L2" and row["city"] == "Toronto"
    }

    assert limits == expected
    assert set(limits.keys()) == {"meals", "hotel", "flight", "ground"}
    for value in limits.values():
        assert isinstance(value, str)


def test_get_policy_limits_not_found_raises_value_error(loaded_db):
    import mcp_server

    with pytest.raises(ValueError):
        mcp_server.get_policy_limits("L9", "Nowhere")


def test_tool_called_before_load_raises_file_not_found_error(tmp_path, monkeypatch):
    import mcp_server

    missing_db = tmp_path / "does-not-exist.db"
    monkeypatch.setattr(mcp_server, "DB_PATH", missing_db)

    with pytest.raises(FileNotFoundError):
        mcp_server.get_claim("CL-2001")
