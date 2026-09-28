"""Tests for Epic 1's decision/clause eval (Story 1-5).

Covers _bmad-output/specs/spec-epic-1/stories/1-5-score-recorded-decisions-against-labelled-csv.md.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
sys.path.insert(0, str(CASE_DIR))


def _load_run_decision_eval():
    # Loaded by path, like tests/test_run_eval.py: eval/ isn't a package and
    # must not go on sys.path, where it could shadow another run_eval module.
    spec = importlib.util.spec_from_file_location(
        "run_decision_eval", CASE_DIR / "eval" / "run_decision_eval.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def decision_eval(tmp_path, monkeypatch):
    import load_seed
    import mcp_server

    run_decision_eval = _load_run_decision_eval()

    db_path = tmp_path / "app.db"
    monkeypatch.setattr(load_seed, "DB_PATH", db_path)
    monkeypatch.setattr(mcp_server, "DB_PATH", db_path)
    monkeypatch.setattr(run_decision_eval.run_eval, "DB_PATH", db_path)
    return run_decision_eval


@pytest.fixture()
def full_run(decision_eval, fake_llm):
    import load_seed
    import run_agent

    load_seed.load_seed()
    run_agent.run(llm=fake_llm)
    return decision_eval.run_eval.DB_PATH


def _set_decision(db_path, line_id, decision, clause):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE decisions SET decision = ?, clause = ? WHERE line_id = ?",
            (decision, clause, line_id),
        )
        conn.commit()


def test_full_run_scores_decision_and_clause_at_100_percent(decision_eval, full_run, capsys):
    checks = decision_eval.evaluate()

    assert [(c.name, c.passed, c.total) for c in checks] == [
        ("decision match (per line item)", 119, 119),
        ("clause match (per line item)", 119, 119),
    ]
    assert decision_eval.main() == 0
    out = capsys.readouterr().out
    assert "reimbursable total" not in out  # Epic 2's check, not reported here
    assert "All checks passed." in out


def test_agrees_with_run_eval_on_a_tampered_run(decision_eval, full_run, capsys):
    _set_decision(full_run, "L-3001", "reject", "3.1")

    epic_1 = {c.name: c.mismatches for c in decision_eval.evaluate()}
    full = {c.name: c.mismatches for c in decision_eval.run_eval.evaluate()}

    assert epic_1["decision match (per line item)"] == ["L-3001: expected approve, got reject"]
    assert epic_1["clause match (per line item)"] == ["L-3001: expected 2.3, got 3.1"]
    assert all(full[name] == mismatches for name, mismatches in epic_1.items())
    assert decision_eval.main() == 1
    out = capsys.readouterr().out
    assert "FAIL  decision match (per line item): 118/119" in out
    assert "      L-3001: expected approve, got reject" in out
    assert "Some checks failed." in out


def test_wrong_clause_alone_fails_only_the_clause_check(decision_eval, full_run):
    _set_decision(full_run, "L-3001", "approve", "2.2")

    decision_check, clause_check = decision_eval.evaluate()

    assert decision_check.ok
    assert clause_check.mismatches == ["L-3001: expected 2.3, got 2.2"]


def test_partial_run_refuses_to_score(decision_eval, full_run, capsys):
    with sqlite3.connect(full_run) as conn:
        conn.execute("DELETE FROM decisions WHERE line_id = 'L-3001'")
        conn.commit()

    assert decision_eval.main() == 2
    assert "partial run is not eval-safe" in capsys.readouterr().err


def test_missing_db_refuses_to_score(decision_eval, capsys):
    assert decision_eval.main() == 2
    assert "not found" in capsys.readouterr().err
    assert not decision_eval.run_eval.DB_PATH.exists()


def test_refuses_to_report_success_when_checks_go_missing(decision_eval, full_run, monkeypatch):
    real_evaluate = decision_eval.run_eval.evaluate
    monkeypatch.setattr(
        decision_eval.run_eval, "evaluate",
        lambda: [c for c in real_evaluate() if not c.name.startswith("clause match")],
    )

    assert decision_eval.main() == 2
