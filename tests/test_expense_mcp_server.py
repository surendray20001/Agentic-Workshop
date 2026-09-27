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


def test_record_decision_creates_table_and_inserts_row(loaded_db):
    import sqlite3

    import mcp_server

    mcp_server.record_decision("L-3001", "approve", "2.3")

    with sqlite3.connect(loaded_db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM decisions")]

    assert rows == [{"line_id": "L-3001", "decision": "approve", "clause": "2.3"}]


def test_record_decision_is_idempotent_upsert(loaded_db):
    import sqlite3

    import mcp_server

    mcp_server.record_decision("L-3001", "flag", "1.3")
    mcp_server.record_decision("L-3001", "approve", "2.3")

    with sqlite3.connect(loaded_db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM decisions")]

    assert rows == [{"line_id": "L-3001", "decision": "approve", "clause": "2.3"}]


def test_record_decision_rejects_invalid_decision_value(loaded_db):
    import mcp_server

    with pytest.raises(ValueError):
        mcp_server.record_decision("L-3001", "aproved", "2.3")


def test_500_gate_is_a_derived_join_not_a_stored_column(loaded_db):
    """The $500 gate has no dedicated column or tool -- prove it's derivable via a join.

    Uses CL-2001's real line items for the approve-over/at-$500 cases, plus one
    hand-built reject-over-$500 line item so the "excluded regardless of amount
    unless decision='approve'" case is deterministic rather than depending on
    CL-2001 happening to have a second item over $500 (it doesn't).
    """
    import sqlite3
    from decimal import Decimal

    import mcp_server

    claim = mcp_server.get_claim("CL-2001")
    line_items = claim["line_items"]
    assert len(line_items) >= 2, "need at least 2 line items on CL-2001 to exercise both sides of the gate"

    over_500 = next(
        (li for li in line_items if Decimal(li["amount"]) > 500), None
    )
    assert over_500 is not None, "expected at least one CL-2001 line item over $500 in the seed data"
    at_or_under_500 = min(line_items, key=lambda li: Decimal(li["amount"]))
    assert Decimal(at_or_under_500["amount"]) <= 500

    mcp_server.record_decision(over_500["line_id"], "approve", "2.3")
    mcp_server.record_decision(at_or_under_500["line_id"], "approve", at_or_under_500["category"])
    # Hand-built: a rejected decision on an over-$500 line item must not appear
    # in the gate either -- the gate is decision='approve' AND amount>500, not
    # just amount>500. line_id doesn't need to exist in line_items for this
    # SQL-level proof (the join naturally drops it if absent), but for a
    # cleaner test we point it at a known line item and only vary the decision.
    mcp_server.record_decision(over_500["line_id"], "reject", "2.3")

    with sqlite3.connect(loaded_db) as conn:
        conn.row_factory = sqlite3.Row
        approved = [
            dict(r)
            for r in conn.execute(
                "SELECT d.line_id, li.amount FROM decisions d "
                "JOIN line_items li ON li.line_id = d.line_id "
                "WHERE d.decision = 'approve'"
            )
        ]
    pending_ids = {r["line_id"] for r in approved if Decimal(r["amount"]) > 500}

    # over_500's last recorded decision was 'reject' (upsert), so it must not
    # be pending even though its amount is over $500.
    assert over_500["line_id"] not in pending_ids
    assert at_or_under_500["line_id"] not in pending_ids

    # Re-approve it to prove the approve+over-500 case is included.
    mcp_server.record_decision(over_500["line_id"], "approve", "2.3")
    with sqlite3.connect(loaded_db) as conn:
        conn.row_factory = sqlite3.Row
        approved = [
            dict(r)
            for r in conn.execute(
                "SELECT d.line_id, li.amount FROM decisions d "
                "JOIN line_items li ON li.line_id = d.line_id "
                "WHERE d.decision = 'approve'"
            )
        ]
    pending_ids = {r["line_id"] for r in approved if Decimal(r["amount"]) > 500}
    assert over_500["line_id"] in pending_ids
    assert at_or_under_500["line_id"] not in pending_ids
