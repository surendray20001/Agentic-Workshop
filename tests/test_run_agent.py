"""Integration test for Case Expenses' full orchestration run (Story 1-4).

Covers the I/O & Edge-Case Matrix in
_bmad-output/specs/spec-epic-1/stories/1-4-orchestrate-full-run.md.
"""

import csv
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import pytest

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
SEED_DIR = CASE_DIR / "seed"
EVAL_DIR = CASE_DIR / "eval"

sys.path.insert(0, str(CASE_DIR))


@pytest.fixture()
def loaded_db(tmp_path, monkeypatch):
    """Load the real seed data into a throwaway app.db for each test.

    Only app.db is a throwaway path (via DB_PATH monkeypatching) -- run_agent's
    claim enumeration reads the real, read-only cases/expense/seed/claims.csv
    directly, same as every other test file in this suite reads real seed CSVs.
    """
    db_path = tmp_path / "app.db"

    import load_seed
    import mcp_server

    monkeypatch.setattr(load_seed, "DB_PATH", db_path)
    monkeypatch.setattr(mcp_server, "DB_PATH", db_path)

    load_seed.load_seed()

    return db_path


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _snapshot_decisions(db_path) -> dict[str, tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return {
            row["line_id"]: (row["decision"], row["clause"])
            for row in conn.execute("SELECT * FROM decisions")
        }


def test_full_run_records_one_decision_per_line_item(loaded_db):
    import run_agent

    recorded = run_agent.run()

    assert recorded == 159
    assert len(_snapshot_decisions(loaded_db)) == 159


def test_full_run_matches_labelled_set_exactly(loaded_db):
    import run_agent

    run_agent.run()
    decisions = _snapshot_decisions(loaded_db)

    labels = _read_csv(EVAL_DIR / "labelled.csv")
    assert len(labels) == 119

    mismatches = [
        label
        for label in labels
        if decisions.get(label["line_id"]) != (label["expected_decision"], label["expected_clause"])
    ]
    assert mismatches == [], f"{len(mismatches)} mismatches: {mismatches[:5]}"


def test_holdout_claims_still_get_decisions(loaded_db):
    import run_agent

    run_agent.run()
    decisions = _snapshot_decisions(loaded_db)

    labels = _read_csv(EVAL_DIR / "labelled.csv")
    all_items = _read_csv(SEED_DIR / "line_items.csv")
    labelled_ids = {row["line_id"] for row in labels}
    holdout_ids = {row["line_id"] for row in all_items} - labelled_ids

    assert len(holdout_ids) == 159 - 119
    for line_id in holdout_ids:
        assert line_id in decisions


def test_second_run_leaves_decisions_unchanged(loaded_db):
    import run_agent

    run_agent.run()
    first = _snapshot_decisions(loaded_db)

    run_agent.run()
    second = _snapshot_decisions(loaded_db)

    assert first == second


def test_run_truncates_stale_decisions_before_repopulating(loaded_db):
    """Proves truncate_decisions() actually matters -- a stale row from a prior
    (e.g. partial/debug) run must not survive a fresh full run."""
    import mcp_server
    import run_agent

    with sqlite3.connect(loaded_db) as conn:
        mcp_server._ensure_decisions_table(conn)
        conn.execute(
            "INSERT INTO decisions (line_id, decision, clause) VALUES (?, ?, ?)",
            ("LI-STALE-NOT-A-REAL-LINE", "approve", "9.9"),
        )
        conn.commit()

    run_agent.run()

    assert "LI-STALE-NOT-A-REAL-LINE" not in _snapshot_decisions(loaded_db)


def test_limits_by_city_builds_an_entry_per_distinct_city():
    """Direct unit test of the orchestration-layer helper for the multi-city
    case the spec requires but no real claim currently exercises."""
    import run_agent

    class _FakeMcpServer:
        def get_policy_limits(self, level, city):
            return {"hotel": "200"} if city == "Toronto" else {"hotel": "150"}

    original = run_agent.mcp_server
    run_agent.mcp_server = _FakeMcpServer()
    try:
        limits_by_city = run_agent._limits_by_city("L2", {"Toronto", "Montreal"})
    finally:
        run_agent.mcp_server = original

    assert set(limits_by_city.keys()) == {"Toronto", "Montreal"}
    assert limits_by_city["Toronto"]["hotel"] == Decimal("200")
    assert limits_by_city["Montreal"]["hotel"] == Decimal("150")
