---
title: 'MCP server: claim context tools'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md', '{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
baseline_commit: 'c0fd5ecc56f70f8cb776a3fd6fc20b0c1fc0a75f'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Case Expenses' agent needs real claim, employee, and limit data to decide line items against `POLICY.md`, but no database or MCP tools exist yet for this case.

**Approach:** Load `cases/expense/seed/*.csv` into a new SQLite database (`cases/expense/app.db`), then expose `get_claim`, `get_employee`, and `get_policy_limits` as MCP tools over it, following the pattern already established in `mcp/triage_server.py`.

## Boundaries & Constraints

**Always:** `get_claim(claim_id)` returns the claim's `employee_id` and all of its line items (every `line_items.csv` column). `get_employee(employee_id)` returns `level` and `city`. `get_policy_limits(level, city)` returns `{category: limit}` for all four categories, amounts as decimal-safe strings (never native float). `load_seed.py` is idempotent — running it twice yields an identical database. This case's database is `cases/expense/app.db`, isolated from the root `app.db`. `cases/expense/seed/*.csv` are read-only. Tests live at repo root under `tests/` (e.g. `tests/test_expense_mcp_server.py`), matching `pyproject.toml`'s existing `testpaths = ["tests"]` — no config changes.

**Never:** Do not implement decision logic, `record_decision`, or the $500 gate — those are Stories 1-2 and 1-3. Do not add a fifth MCP tool. Do not touch `mcp/triage_server.py`, or any root `app.db`/`mcp/`/`run_agent.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `get_claim` happy path | `claim_id="CL-2001"` | Returns `employee_id` and all line items for that claim, amounts as decimal-safe strings | N/A |
| `get_claim` not found | `claim_id="CL-9999"` | — | Raises `ValueError`, matching `triage_server.py` |
| `get_employee` happy path | `employee_id="E-101"` | Returns `level`, `city` | N/A |
| `get_employee` not found | `employee_id="E-999"` | — | Raises `ValueError` |
| `get_policy_limits` happy path | `level="L2", city="Toronto"` | Returns all four categories' limits, matching `limits.csv` | N/A |
| `get_policy_limits` not found | level/city combo absent from seed data | — | Raises `ValueError` (defensive; current data covers every combo) |
| `load_seed.py` re-run | run twice | Second run produces an identical database (drop-and-recreate) | N/A |
| Tool called before load | `app.db` missing | — | Raises `FileNotFoundError` telling the user to run `load_seed.py` first, matching `triage_server.py` |

</frozen-after-approval>

## Code Map

- `mcp/triage_server.py` — reference pattern: `FastMCP` server, `sqlite3.Row`-based `_query` helper, `ValueError` for not-found, `DB_PATH` via `Path(__file__).resolve().parent / "app.db"`. Reuse this shape; do not modify this file.
- `pyproject.toml` — confirms `mcp>=1.9` (installed: 1.30.0) and pytest `testpaths = ["tests"]`; add no new dependency.
- `cases/expense/seed/claims.csv` — `claim_id, employee_id, submitted_at, purpose` (40 rows).
- `cases/expense/seed/employees.csv` — `employee_id, name, level, city, department` (12 rows).
- `cases/expense/seed/limits.csv` — `level, city, category, limit_cad` (80 rows: 4 levels × 5 cities × 4 categories; every combo present).
- `cases/expense/seed/line_items.csv` — `line_id, claim_id, date, city, category, merchant, amount, has_receipt, description` (159 rows).
- `_bmad-output/specs/spec-epic-1/SPEC.md` — CAP-1 (this story) and constraints AD-2, AD-5, AD-6, AD-8, AD-11.

## Tasks & Acceptance

**Execution:**
- [x] `cases/expense/load_seed.py` -- load the four CSVs into `cases/expense/app.db` as `claims`, `employees`, `limits`, `line_items` tables with the same columns as the CSVs; drop-and-recreate each table so re-running gives an identical database -- idempotent loading, isolated from root `app.db`.
- [x] `cases/expense/mcp_server.py` -- FastMCP server exposing `get_claim`, `get_employee`, `get_policy_limits`, following `mcp/triage_server.py`'s pattern -- CAP-1, AD-5, AD-11.
- [x] `tests/test_expense_mcp_server.py` -- unit tests covering the I/O & Edge-Case Matrix above.

**Acceptance Criteria:**
- Given `cases/expense/app.db` does not exist, when `uv run python cases/expense/load_seed.py` runs, then it creates the database with `claims`, `employees`, `limits`, `line_items` tables matching the CSV row counts (40, 12, 80, 159).
- Given the database already exists, when `load_seed.py` runs again, then the resulting database is identical in content to the first run.
- Given the database is loaded, when `get_claim("CL-2001")` is called, then it returns `employee_id "E-101"` and every line item on that claim with all seed columns, amounts as decimal-safe strings.
- Given the database is loaded, when `get_policy_limits("L2", "Toronto")` is called, then it returns all four categories' limits exactly matching `limits.csv`.
- Given an unknown `claim_id`, `employee_id`, or level/city combination, when the corresponding tool is called, then it raises `ValueError`.

## Implementation Notes

## Spec Change Log

## Review Triage Log

- **[blind-hunter] get_claim docstring promises "every seed column" but no test asserts `submitted_at`/`purpose` pass through** — verdict: `low`. Verified: `get_claim("CL-2001")` does return `submitted_at`/`purpose` (checked directly); the test only asserts `employee_id` and line items, not the claim's own remaining columns. Real, trivial-to-fix gap → routes to patch.
- **[edge-case] load_seed.py: missing CSV file in TABLES → unhandled FileNotFoundError** — verdict: `low`, rejected. Seed CSVs are read-only, fixed, and already verified to load correctly; unreachable in normal use, and Python's own FileNotFoundError already names the missing path.
- **[edge-case] load_seed.py: CSV row missing/extra column → uncaught KeyError** — verdict: `low`, rejected. Same read-only/fixed-data reasoning; unreachable given current seed files.
- **[blind-hunter] load_seed.py stores everything as TEXT with no validation of malformed amount/has_receipt values** — verdict: `low`, rejected. Same root cause as the two findings above (no CSV validation); unreachable given read-only, already-verified seed data.
- **[edge-case] load_seed.py: exception mid-loop leaves DB partially recreated** + **[edge-case] mcp_server.py: corrupt/empty app.db raises raw sqlite3.OperationalError instead of FileNotFoundError** + **[blind-hunter] same OperationalError-leak concern** — verdict: `low`, rejected (grouped, shared root cause: no transactional safety net around `load_seed.py`/no db-health check in `mcp_server.py`). Unlikely given fixed seed data and a successful verified run; self-healing via re-running `load_seed.py`. Fix requires added guards/rollback logic, not a direct correction.
- **[blind-hunter] get_policy_limits doesn't enforce exactly 4 categories if limits.csv changes** — verdict: `low`, rejected. `limits.csv` is read-only; verified 80 rows = 4 levels × 5 cities × 4 categories with zero gaps.
- **[edge-case] limits table duplicate (level, city, category) rows → dict comprehension silently drops one** — verdict: `low`, rejected. Verified zero duplicate rows exist in `limits.csv`; unreachable given read-only data.
- **[blind-hunter] no test for a claim with zero line items** — verdict: `low`, rejected. Verified: no such claim exists in the current (fixed, read-only) seed data; testing it would require synthetic data, more than a direct correction.
- **[blind-hunter] sys.path.insert collision risk with a future cases/leads/mcp_server.py of the same module name** — verdict: `false`. No second same-named module exists in the repo; the claimed collision cannot occur today. Worth a mental note for whoever builds the leads case later, but not a defect in this diff.
- **[blind-hunter] idempotency test's rowid-ordering assumption is undocumented/fragile** — verdict: `false`. Both snapshots in the test are produced by the same deterministic code path within one test run; if insertion order ever became non-deterministic, the test would correctly fail rather than falsely pass. No coupling bug exists.
- **[blind-hunter] no case-sensitivity handling for level/city (e.g. "toronto" vs "Toronto")** — verdict: `low`, rejected. Confirmed real (SQLite TEXT comparison is case-sensitive), but the only intended call chain (`get_employee` → `get_policy_limits`) always passes already-correctly-cased data straight through; not a user-facing input surface.
- **[verification-gap]** — no findings; all 9 tests independently confirmed passing and exercising real (non-mocked) code paths matching the I/O matrix.

## Verification

**Commands:**
- `uv run python cases/expense/load_seed.py` -- expected: creates/overwrites `cases/expense/app.db` with 4 tables, row counts 40/12/80/159.
- `uv run pytest tests/test_expense_mcp_server.py` -- expected: all tests pass.
