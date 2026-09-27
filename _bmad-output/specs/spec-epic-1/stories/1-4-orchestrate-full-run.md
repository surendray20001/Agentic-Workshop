---
title: 'Orchestrate a full run over all 40 claims'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md', '{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
baseline_commit: 'd7e0cb4b09f1409eb4d490d4d2eeb3713ae271c7'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Stories 1-1 through 1-3 built the pieces (context tools, decision engine, recording) but nothing yet drives them over every claim — Epic 1's own success signal ("for all 40 claims, every recorded decision resolves POLICY.md") isn't achievable without a runner.

**Approach:** Build `cases/expense/run_agent.py`: a deterministic driver (no LLM, no LangChain, no MLflow — that's Epic 2's CAP-7) that truncates `decisions`, then for every claim assembles context via the Story 1-1 tools, decides via Story 1-2's engine, and records via Story 1-3's tool. Epic 2 extends this same file to add explanation generation; it does not replace it.

## Boundaries & Constraints

**Always:** `run_agent.py` reads claim IDs from `cases/expense/seed/claims.csv` directly (no 5th MCP tool for enumeration). Before processing, it truncates `decisions` (AD-12) via a new `truncate_decisions()` function in `mcp_server.py` (not a registered tool). For each claim, in order: `get_claim`, `get_employee`, then `get_policy_limits(employee["level"], city)` once per distinct city among that claim's line items — building `limits_by_city` — then `decision_engine.decide_claim(line_items, employee, limits_by_city, submitted_at)`, then `record_decision(line_id, decision, clause)` for every line item. Running the script twice must leave `decisions` in the same final state (truncate-then-repopulate makes this true by construction).

**Never:** Do not call any LLM, LangChain, or MLflow API — narration and tracing are Epic 2's scope. Do not modify `decision_engine.py` or the four existing `mcp_server.py` tools' signatures. Do not add a fifth MCP tool.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full run, fresh database | `uv run python cases/expense/run_agent.py` against a freshly loaded `app.db` | `decisions` has exactly one row per line item across all 159 line items in all 40 claims | N/A |
| Full run, decisions already populated | Run again without reloading seed | `decisions` truncated first, then repopulated identically — same final row count and content as the first run | N/A |
| Labelled-set correctness | The 30 labelled claims' resulting `decisions` rows | Decision + clause match `eval/labelled.csv` exactly on all 119 labelled line items | N/A |
| Holdout claims | The 10 unlabelled claims | Still get a `decisions` row per line item (decided, just not checked against a label) | N/A |
| Multi-city claim support | A claim whose line items span more than one city (none exist today, but the code must not assume otherwise) | `limits_by_city` includes an entry for every distinct city among that claim's line items | N/A |

</frozen-after-approval>

## Code Map

- `cases/expense/mcp_server.py` (Story 1-3, done) — add `truncate_decisions()`: `DELETE FROM decisions` if the table exists (no-op if it doesn't yet), plain function, not `@server.tool()`.
- `cases/expense/decision_engine.py` (Story 1-2, done) — `decide_claim(line_items, employee, limits_by_city, submitted_at)`, call directly (no MCP indirection needed; this is a same-process orchestration script, not yet a real LangChain agent).
- `cases/expense/seed/claims.csv` — read directly for the list of 40 `claim_id`s to process, in file order.
- `_bmad-output/specs/spec-epic-1/SPEC.md` — this story completes Epic 1's Success Signal in full.

## Tasks & Acceptance

**Execution:**
- [x] `cases/expense/mcp_server.py` -- add `truncate_decisions()`.
- [x] `cases/expense/run_agent.py` -- orchestrate the full 40-claim run per Boundaries & Constraints.
- [x] `tests/test_run_agent.py` -- integration test: run the full pipeline against a throwaway `app.db`, then assert `decisions` matches `eval/labelled.csv` exactly on all 119 labelled line items, has exactly 159 total rows, and is unchanged in content after a second run.

**Acceptance Criteria:**
- Given a freshly loaded `app.db`, when `run_agent.py` runs, then `decisions` has exactly 159 rows (one per line item across all 40 claims).
- Given the 30 labelled claims' resulting rows, when compared to `eval/labelled.csv`, then decision and clause match exactly on all 119 labelled line items.
- Given `run_agent.py` has already run once, when it runs a second time, then `decisions`' final content is identical to the first run's.

## Implementation Notes

## Spec Change Log

## Review Triage Log

- **[verification-gap] truncate-before-run (AD-12) is never actually exercised by a test that would fail if removed** — verdict: `high` on the gap itself (confirmed: deleting `truncate_decisions`'s `DELETE FROM decisions` would not fail any existing test, since both runs iterate identical claims and `record_decision`'s upsert alone reproduces the same final state). Routes to patch: add a test seeding a stale row before `run()`, asserting it's gone after.
- **[blind-hunter] no direct unit test of `_limits_by_city` with a synthetic multi-city input** — verdict: `low`. The spec explicitly requires the code not assume single-city; `decision_engine.py`'s own multi-city handling is tested (Story 1-2), but this orchestration-layer helper wasn't directly. Cheap fix. Routes to patch.
- **[blind-hunter] `loaded_db` fixture reads the real, read-only `claims.csv`, not a throwaway copy — undocumented, could confuse a future reader into thinking the whole environment is isolated** — verdict: `low`. Intentional and consistent with every other test file's pattern (seed CSVs are read-only fixtures, reused directly), but worth a one-line comment. Routes to patch.
- **[blind-hunter + edge-case] get_policy_limits could raise ValueError for a missing level/city combo, crashing the run mid-loop** — verdict: `low`, rejected. Empirically verified unreachable: all 40 claims already processed successfully end-to-end (159/159 recorded, 0/119 labelled mismatches) via the real seed data, which has complete 4-level × 5-city coverage.
- **[blind-hunter + edge-case] no partial-failure/transaction handling if run() crashes mid-loop** — verdict: `low`, rejected. Same class of finding rejected in Stories 1-1/1-2/1-3: unlikely in this controlled context, fix requires non-trivial transaction/rollback logic across multiple SQLite connections.
- **[blind-hunter] no test verifying `truncate_decisions` isn't registered as an `@server.tool()`** — verdict: `low`, rejected. Would require coupling a test to FastMCP's internal tool-registry API for a regression a future diff review would visually catch immediately.
- **[blind-hunter] magic numbers (159, 119, 30, 10) not centralized in tests** — verdict: `low`, rejected. Matches the established, unflagged pattern from Story 1-1's own row-count test.
- **[blind-hunter + edge-case] no dedup/validation of claim IDs, no test for empty claims.csv** — verdict: `low`, rejected. Read-only, fixed seed data already verified (40 unique rows).
- **[blind-hunter] no test pinning `_claim_ids()`'s file-order preservation** — verdict: `low`, rejected. `csv.DictReader`'s order-preservation is well-known stdlib behavior; low-value meta-test.
- **[blind-hunter] run() returns only an int count, limiting what Epic 2 can build on** — verdict: `low`, rejected. Out of this story's scope; Epic 1's own acceptance criteria are fully satisfied by the int count, and Epic 2's actual needs aren't yet specified.
- **[blind-hunter + edge-case] no test for truncate_decisions()'s FileNotFoundError path** — verdict: `low`, rejected. Already covered: `truncate_decisions` calls the same shared `_require_db()` helper already tested via `get_claim`'s not-loaded case (Story 1-1); no different behavior to re-test.

## Verification

**Commands:**
- `uv run python cases/expense/load_seed.py && uv run python cases/expense/run_agent.py` -- expected: runs to completion, no errors.
- `uv run pytest tests/test_run_agent.py -v` -- expected: all tests pass.
