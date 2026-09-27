---
title: 'Score a run against the labelled set'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-expense-epic-2/SPEC.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nothing yet proves a completed run meets CAP-8's bar. BRIEF.md's code checks (decision match per line item, clause match per line item, reimbursable-total match per claim across the 30 labelled claims) exist only as an ad-hoc test in `tests/test_run_agent.py`, not as the single command the case's `AGENTS.md` documents (`uv run python cases/expense/eval/run_eval.py`).

**Approach:** Add `cases/expense/eval/run_eval.py`, which reads the current `decisions` table in `cases/expense/app.db` and `cases/expense/eval/labelled.csv` (read-only, read directly, never moved into an MLflow dataset). It reports each check as passed/total with PASS/FAIL, lists every mismatch, and exits non-zero on any failure. The reimbursable total follows Spine AD-10: the `Decimal` sum of `line_items.amount` over rows whose decision is `approve`, grouped by `claim_id`, including items still pending the $500 gate. The expected total is derived the same way from the labels' `expected_decision`. The eval scores the current `decisions` state and does not trigger a run. Per AD-12 it refuses to score (non-zero exit, clear message) when `app.db` or the `decisions` table is missing, or when `decisions` does not cover every line item (a partial or debug run). Decisions and the $500 gate are never re-derived, and nothing is written.

</frozen-after-approval>

## Implementation Notes

- Location follows the architecture spine's Structural Seed and `cases/expense/AGENTS.md` (`cases/expense/eval/run_eval.py`); `labelled.csv` in the same folder stays untouched.
- `line_items.amount` is stored as TEXT, so totals are summed in Python `Decimal`, not SQL `SUM` (a float).
- Tests: `tests/test_run_eval.py` — full run scores 100%; a tampered decision/clause is reported and flips that claim's total; a partial `decisions` table and a missing db both refuse to score.
- Verified: `uv run python cases/expense/eval/run_eval.py` on the live Groq run's `app.db` → 119/119, 119/119, 30/30, exit 0 (also from `cases/expense/` as cwd). Full suite: 53 passed, 1 skipped (Gemini daily quota).
- Exit codes: 0 all checks pass, 1 a check failed, 2 cannot score (documented in the module docstring).

## Review Triage Log

- `high` — Spec file ended with leaked tool-call markup (blind-hunter): patched — stripped; status set to `done`.
- `low` — Exit codes 0/1/2 undocumented (blind-hunter): patched — added to `run_eval.py`'s docstring.
- `false` — Per-claim total silently omits a claim's unlabelled line items (blind-hunter): refuted — the 119 labels cover exactly every seed line item of the 30 labelled claims, no duplicates (checked against `seed/line_items.csv`).
- `false` — Reimbursable total isn't an independent check (blind-hunter): refuted as a defect — AD-10 defines the total as this derived query; there is no stored total to compare, and BRIEF's check is exactly "sum of approved items matches".
- `low` — Label `line_id` absent from `line_items` raises `KeyError` instead of a clean refusal; stale extra `decisions` rows unflagged (blind-hunter): not worth fixing — labels and seed are fixed read-only files that match exactly; failure would still be loud; guard adds complexity.
- `low` — Malformed/NULL `amount` raises uncaught `InvalidOperation` (blind-hunter): not worth fixing — amounts come from the read-only seed via `load_seed.py`, all valid.
- `low` — `with sqlite3.connect(...)` doesn't close the connection (blind-hunter): not worth fixing — short-lived CLI, read-only; matches the pattern used throughout `mcp_server.py` and existing tests.
- `low` — Test gaps: no subprocess run of the command, no "writes nothing" check on a full run, `main()`==2 unasserted for the no-table case, $500 test uses a hand-built dict (blind-hunter): not worth fixing — command run end to end manually; the db is opened `mode=ro` so writes are impossible; the gated item's inclusion is also covered by the 30/30 total check on a real run.
- `low` — CLI takes no arguments; success line lacks an overall score (blind-hunter): not worth fixing — the documented single command needs none; each check already prints passed/total.
