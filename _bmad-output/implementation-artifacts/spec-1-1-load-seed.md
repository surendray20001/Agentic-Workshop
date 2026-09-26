---
title: 'Load seed data into app.db'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1's later work (the agent, the eval) needs a local SQLite database of tickets and customers, but nothing yet loads `seed/tickets.csv` and `seed/customers.csv` into one.

**Approach:** Add `load_seed.py` at the repo root. Running `uv run python load_seed.py` reads both CSVs and writes them into `app.db` as a `tickets` table (`ticket_id`, `customer_id`, `created_at`, `text`) and a `customers` table (`customer_id`, `name`, `plan`, `open_tickets`), with the exact table/column names `mcp/triage_server.py` already queries. Running it again drops and recreates both tables from the same CSVs, so the database ends up in the same state (idempotent). No network calls, no API keys, and the CSVs are read-only inputs.

</frozen-after-approval>

## Implementation Notes

- `load_seed.py` drops and recreates both tables on every run (simplest way to guarantee idempotency from static CSVs); inserts happen inside `contextlib.closing(sqlite3.connect(db_path)) as conn, conn:` so the transaction commits and the connection closes automatically.
- `pyproject.toml` gained `pythonpath = ["."]` under `[tool.pytest.ini_options]` — without it, `tests/test_load_seed.py` couldn't import the repo-root `load_seed` module.
- `tests/test_load_seed.py` covers the happy-path schema/values and idempotency (running twice yields the same row counts), using `tmp_path` so tests never touch the real `app.db`.
- Verified manually: `uv run python load_seed.py` run twice produces stable `tickets`/`customers` tables that `mcp/triage_server.py`'s queries (by `ticket_id` / `customer_id`) resolve correctly.

## Review Triage Log

- **medium/low group, patched** — `conn.commit()` was redundant with the `with conn:` context manager, and the connection was never explicitly closed. Fixed with `contextlib.closing(...)`.
- **low, patched** — no comment documented that `tickets`/`customers` column names must exactly match `mcp/triage_server.py`'s queries. Added a one-line comment above the schema.
- **low, rejected** — no custom error handling for malformed CSV rows or missing seed files. `seed/*.csv` are static, read-only workshop fixtures (not user input); a raw `KeyError`/`ValueError`/`FileNotFoundError` already fails loudly and (verified) Python's `FileNotFoundError` already names the missing path. Building custom validation/messaging and its tests is more scope than this story's CAP-1 (load + idempotency) calls for.
- **low, rejected (false)** — flagged lack of a `--db-path` CLI flag / collision guard against an existing `app.db`. This contradicts the spec itself: rerunning must reset to the same state against the fixed `app.db` path; `load_seed(db_path=...)` is already parametrized for tests.
- **medium, deferred** — no FK constraint or cross-CSV referential-integrity check between `tickets.customer_id` and `customers.customer_id`, plus a table-creation-order note in case an FK is added later. Real idea, not required by CAP-1's success criteria, and not caused by this change — logged in `deferred-work.md`.
- **false, out of scope** — reviewer noted `.env.example` shows deleted in the working tree. Predates this story's changes (present before `load_seed.py` was written) and the human already decided during context-gathering to leave it as-is; not part of this diff.
