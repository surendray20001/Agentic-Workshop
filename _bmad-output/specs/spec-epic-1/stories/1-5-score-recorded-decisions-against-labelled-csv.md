---
title: 'Score recorded decisions against labelled.csv'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1's CAP-8 (decision and clause match only) has no Epic 1 command of its own. The scoring logic already exists in `cases/expense/eval/run_eval.py` (Story 2-2), but that command also reports Epic 2's reimbursable-total check.

**Approach:** Add a thin Epic 1 entry point, `cases/expense/eval/run_decision_eval.py`, that reuses `run_eval.evaluate()` rather than writing a second scorer. It reports only decision match and clause match (passed/total, PASS/FAIL, every mismatch) across the 119 labelled line items. Exit codes: 0 when both checks pass, 1 when either fails, and 2 when it cannot score. It refuses to score a missing db or a partial `decisions` table, as `run_eval.py` already does. It is read-only. `run_eval.py` and Story 2-2's behavior are unchanged.

</frozen-after-approval>

## Implementation Notes

- `cases/expense/eval/run_decision_eval.py` loads its sibling `run_eval.py` by path and filters `evaluate()` to the decision and clause checks; `run_eval.py` is unchanged. Tests: `tests/test_run_decision_eval.py` (6), also loaded by path so `eval/` never goes on `sys.path`.
- Trade-off accepted: reusing `run_eval.evaluate()` means an exception in Epic 2's reimbursable-total path would also stop this command; factoring the per-line checks out would change `run_eval.py`, which this story leaves alone.
- Verified: real `app.db` → decision 119/119, clause 119/119, exit 0 (also from `cases/expense/` as cwd). Full suite 59 passed.

## Review Triage Log

- `medium` — Filtered result could be empty (a check renamed in `run_eval.py`) and still print "All checks passed" with exit 0 (blind-hunter): patched — `evaluate()` raises `NotEvalReady` (exit 2) unless both checks come back; test added.
- `medium` — Test put `cases/expense/eval/` on `sys.path` for the whole session, so any later `import run_eval` (e.g. Saturday's root `eval/run_eval.py` once merged) resolves to the expense scorer (blind-hunter): patched — module and test both load by path.
- `low` — Bare `import run_eval` only works with the script's folder on `sys.path` (blind-hunter): patched with the same by-path load.
- `low` — Printed FAIL/mismatch lines never asserted (blind-hunter): patched — the tampered-run test now asserts them.
- `low` — Other failures (missing labels CSV, corrupt db, KeyError) exit 1 via traceback, not 2 (blind-hunter): not worth fixing — inputs are fixed read-only files; failure is loud; `run_eval.py` behaves the same.
- `low` — Epic 2's total path can break this command (blind-hunter): accepted trade-off, recorded above.
- `low` — Print/exit loop repeats `run_eval.main()`'s six lines (blind-hunter): not worth fixing — sharing it needs a change to `run_eval.py`, out of this story.
- `low` — No subprocess test; untested no-table / decision-only cases; no read-only hash check; hard-coded 119; no output header (blind-hunter): not worth fixing — command run end to end manually; db opened `mode=ro`; those paths are covered by `run_eval.py`'s own tests.
- `false` — Story missing tasks/ACs/verification sections (blind-hunter): refuted — the one-shot route deletes those sections by design.
- `defer` — `cases/expense/AGENTS.md` doesn't list the new command (blind-hunter): deferred — edits an agent-context file.

