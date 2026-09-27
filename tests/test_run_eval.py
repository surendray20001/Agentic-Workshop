"""Tests for Case Expenses' eval script (Story 2-2).

Covers _bmad-output/specs/spec-expense-epic-2/stories/2-2-score-a-run-against-the-labelled-set.md.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
sys.path.insert(0, str(CASE_DIR))


def _load_run_eval():
    # cases/expense/eval/ isn't a package (and `eval` shadows a builtin), so load by path.
    spec = importlib.util.spec_from_file_location("run_eval", CASE_DIR / "eval" / "run_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def run_eval(tmp_path, monkeypatch):
    import load_seed
    import mcp_server

    db_path = tmp_path / "app.db"
    monkeypatch.setattr(load_seed, "DB_PATH", db_path)
    monkeypatch.setattr(mcp_server, "DB_PATH", db_path)
    module = _load_run_eval()
    monkeypatch.setattr(module, "DB_PATH", db_path)
    return module


@pytest.fixture()
def full_run(run_eval, fake_llm):
    import load_seed
    import run_agent

    load_seed.load_seed()
    run_agent.run(llm=fake_llm)
    return run_eval.DB_PATH


def _set_decision(db_path, line_id, decision, clause):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE decisions SET decision = ?, clause = ? WHERE line_id = ?",
            (decision, clause, line_id),
        )
        conn.commit()


def test_full_run_scores_every_check_at_100_percent(run_eval, full_run, capsys):
    checks = run_eval.evaluate()

    assert [(c.passed, c.total) for c in checks] == [(119, 119), (119, 119), (30, 30)]
    assert run_eval.main() == 0
    assert "All checks passed." in capsys.readouterr().out


def test_wrong_decision_is_reported_and_flips_that_claims_total(run_eval, full_run, capsys):
    # L-3001 (CL-2001) is labelled approve / 2.3; rejecting it drops its amount from the total.
    _set_decision(full_run, "L-3001", "reject", "3.1")

    decision_check, clause_check, total_check = run_eval.evaluate()

    assert decision_check.mismatches == ["L-3001: expected approve, got reject"]
    assert clause_check.mismatches == ["L-3001: expected 2.3, got 3.1"]
    assert len(total_check.mismatches) == 1
    assert total_check.mismatches[0].startswith("CL-2001:")
    assert run_eval.main() == 1
    assert "FAIL  decision match (per line item): 118/119" in capsys.readouterr().out


def test_wrong_clause_alone_fails_only_the_clause_check(run_eval, full_run):
    _set_decision(full_run, "L-3001", "approve", "2.2")

    decision_check, clause_check, total_check = run_eval.evaluate()

    assert decision_check.ok and total_check.ok
    assert clause_check.mismatches == ["L-3001: expected 2.3, got 2.2"]


def test_partial_run_refuses_to_score(run_eval, full_run, capsys):
    with sqlite3.connect(full_run) as conn:
        conn.execute("DELETE FROM decisions WHERE line_id = 'L-3001'")
        conn.commit()

    with pytest.raises(run_eval.NotEvalReady, match="158 of 159"):
        run_eval.evaluate()
    assert run_eval.main() == 2
    assert "partial run is not eval-safe" in capsys.readouterr().err


def test_seed_loaded_but_agent_never_run_refuses_to_score(run_eval):
    import load_seed

    load_seed.load_seed()

    with pytest.raises(run_eval.NotEvalReady, match="no decisions table"):
        run_eval.evaluate()


def test_missing_db_refuses_to_score_without_creating_it(run_eval):
    with pytest.raises(run_eval.NotEvalReady, match="not found"):
        run_eval.evaluate()
    assert not run_eval.DB_PATH.exists()


def test_approved_item_over_500_still_counts_toward_the_total(run_eval, full_run):
    """AD-10: items pending the $500 gate are reimbursable. L-3001 is a $546.57 approve."""
    decisions, line_items = run_eval._read_db()
    assert decisions["L-3001"][0] == "approve"
    assert line_items["L-3001"][1] > 500

    totals = run_eval._reimbursable_totals({"L-3001": "approve"}, line_items)

    assert totals["CL-2001"] == line_items["L-3001"][1]
