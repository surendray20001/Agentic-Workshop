---
title: 'Record decisions idempotently, with the $500 gate'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md', '{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
baseline_commit: 'e1b2534eae16d3dfcb224203eab495131b62da67'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Decisions from Story 1-2's decision engine have nowhere to be recorded, and there's no way to tell which approved items are awaiting a person's $500+ sign-off.

**Approach:** Add `record_decision` as the fourth (and final) MCP tool — an idempotent upsert into a new `decisions` table. The $500 gate needs no new column or table: it is a derived condition (`decision='approve' AND line item amount > 500`), proven by a join query in tests, not new production code.

## Boundaries & Constraints

**Always:** `record_decision(line_id, decision, clause)` writes exactly those three columns to `decisions`, via `INSERT ... ON CONFLICT(line_id) DO UPDATE`, with `line_id` as the table's primary key — calling it twice for the same `line_id` leaves one row, with the second call's values. The `decisions` table is created (`CREATE TABLE IF NOT EXISTS`) by `mcp_server.py` itself if it doesn't already exist — `load_seed.py` (Story 1-1) is not touched. The $500 gate is always computed by joining `decisions` to `line_items` on `line_id` and filtering `decision='approve' AND CAST(amount AS REAL) > 500` (or equivalent `Decimal` comparison in Python) — never a stored column, never a fourth `decision` value.

**Never:** Do not add a fifth MCP tool for querying pending approvals. Do not add a column to `decisions` beyond `line_id`, `decision`, `clause`. Do not implement payout/release logic — this system only ever identifies what's pending; a person acts on it outside this system. Do not modify `cases/expense/load_seed.py` or `cases/expense/decision_engine.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First record for a line | `record_decision("L-3001", "approve", "2.3")` on a fresh `decisions` table | Row inserted; one row exists for `L-3001` | N/A |
| Re-record same line (idempotent) | `record_decision("L-3001", "approve", "2.3")` called again, then with different values | Still exactly one row for `L-3001`; final row reflects the latest call's values | N/A |
| `decisions` table doesn't exist yet | First-ever `record_decision` call against a fresh `app.db` | Table is created automatically; call succeeds | N/A |
| $500 gate: approve over $500 | A `decisions` row with `decision='approve'` whose line item's `amount` > 500 | Included in the derived pending-approval join | N/A |
| $500 gate: approve at/under $500 | `decision='approve'`, `amount` ≤ 500 | Excluded from the derived pending-approval join | N/A |
| $500 gate: flag/reject over $500 | `decision` is `flag` or `reject`, `amount` > 500 | Excluded — the gate only applies to `approve` decisions | N/A |

</frozen-after-approval>

## Code Map

- `cases/expense/mcp_server.py` (Story 1-1, done) — add `record_decision` alongside the existing `get_claim`/`get_employee`/`get_policy_limits` tools, reusing the module's `DB_PATH`/`_query` pattern; add a small `_ensure_decisions_table(conn)` helper called before the upsert.
- `tests/test_expense_mcp_server.py` (Story 1-1, done) — extend with `record_decision` and $500-gate tests using the existing `loaded_db` fixture; do not restructure existing tests.
- `_bmad-output/specs/spec-epic-1/SPEC.md` — CAP-5, CAP-6 (this story) and constraints AD-2, AD-3, AD-9.

## Tasks & Acceptance

**Execution:**
- [x] `cases/expense/mcp_server.py` -- add `record_decision(line_id, decision, clause)` as an MCP tool: create `decisions` table if missing (`line_id TEXT PRIMARY KEY, decision TEXT, clause TEXT`), upsert via `ON CONFLICT(line_id) DO UPDATE`.
- [x] `tests/test_expense_mcp_server.py` -- tests covering the I/O & Edge-Case Matrix above, including a raw SQL join proving the $500 gate is correctly derivable (no stored gate state).

**Acceptance Criteria:**
- Given a fresh database, when `record_decision("L-3001", "approve", "2.3")` is called, then `decisions` has exactly one row for `L-3001` with those values.
- Given a line already has a recorded decision, when `record_decision` is called again for the same `line_id` with different values, then `decisions` still has exactly one row for that `line_id`, reflecting the latest call.
- Given a mix of recorded decisions across several line items with varying amounts and decisions, when the $500-gate join query runs, then it returns exactly the line items where `decision='approve'` and `amount > 500`, and no others.

## Implementation Notes

## Spec Change Log

## Review Triage Log

- **[blind-hunter + edge-case] record_decision doesn't validate decision against {approve, flag, reject}** — verdict: `low`. Unlikely once Story 1-4 wires the only intended caller (decision_engine.py's fixed output), but the fix is a trivial one-line check — doesn't meet the "fix is more than direct correction" bar for rejecting a low finding. Routes to patch.
- **[blind-hunter] test's $500-gate join uses `CAST(amount AS REAL)`, inconsistent with the codebase's Decimal-safety convention (AD-8)** — verdict: `low`. Test-only code, but sets a bad precedent a future maintainer could copy into production. Trivial fix (filter in Python with Decimal instead of SQL CAST). Routes to patch.
- **[edge-case] StopIteration risk in test's `next()` call with no default if no CL-2001 line item exceeds $500** — verdict: `low`. Confirmed real: `CL-2001` has exactly one item over $500 today, so it currently passes, but a bare `next()` with no default would fail opaquely if seed data changed. Trivial fix. Routes to patch.
- **[blind-hunter] `test_500_gate_is_a_derived_join_not_a_stored_column`'s "reject/flag over $500 excluded" assertion is conditional on `other_over_500` existing, and it never does** — verdict: `low`, confirmed via direct check: `CL-2001` has exactly one item over $500 (`L-3001`), so that branch never executes. Trivial fix: use a deterministic hand-built case instead of depending on real claim data shape. Routes to patch.
- **[blind-hunter] FileNotFoundError check duplicated between `_query` and `record_decision` instead of a shared helper** — verdict: `low`. Real duplication, trivial extraction, reduces code rather than adding it. Routes to patch.
- **[blind-hunter + edge-case] no FK check that line_id exists in line_items** — verdict: `low`, rejected. Unlikely given the only intended caller sources `line_id` from `get_claim`'s real output; fix requires an extra query per call, more than a direct correction.
- **[blind-hunter + edge-case] unhandled sqlite3.Error / TOCTOU on DB_PATH.exists() then connect()** — verdict: `low`, rejected. Same pattern as the pre-existing, already-accepted `_query` helper from Story 1-1; narrow race window in a single-user workshop context; fix adds non-trivial error-handling complexity.
- **[blind-hunter + edge-case] no validation of empty-string line_id/clause, no test for invalid input shapes** — verdict: `low`, rejected. Same reasoning: only intended caller passes real, valid values.
- **[blind-hunter] race condition between CREATE TABLE and INSERT under concurrent calls** — verdict: `low`, rejected. No concurrent-writer scenario exists in this single-agent workshop context; fix requires non-trivial locking/transaction logic.
- **[blind-hunter] docstring doesn't document empty/malformed clause behavior** — verdict: `low`, rejected. Doc completeness nice-to-have; data flow is controlled by the intended caller.
- **[blind-hunter] no test exercises record_decision through the actual FastMCP tool-invocation/serialization path** — verdict: `low`, rejected. Matches the established, unflagged convention for all three pre-existing tools in this same file since Story 1-1.
- **[blind-hunter] no logging/observability for recorded decisions** — verdict: `low`, rejected. No logging requirement exists anywhere in the PRD/SPEC for this case; out of scope.
- **[blind-hunter] `_ensure_decisions_table` not directly unit-tested in isolation** — verdict: `low`, rejected. Already indirectly covered: `test_record_decision_is_idempotent_upsert` calls it twice via two `record_decision` calls, proving `IF NOT EXISTS` doesn't error on the second call.
- **[verification-gap]** — no findings; all 12 tests independently confirmed passing, exercising the real upsert and derived-join behavior against real seed data.

## Verification

**Commands:**
- `uv run pytest tests/test_expense_mcp_server.py -v` -- expected: all tests pass (existing Story 1-1 tests plus new ones).
