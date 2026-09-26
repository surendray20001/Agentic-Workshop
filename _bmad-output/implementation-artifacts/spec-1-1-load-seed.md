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

### bmad-code-review pass (branch vs main)

- **low, patched** — `_read_csv` opened files with the platform default encoding instead of `encoding="utf-8"`; a latent portability gap (currently unreachable — seed CSVs are pure ASCII). Fixed.
- **low, patched** — `load_seed()` had no docstring, and the CLI entry point's `print` gave no row-count confirmation. Added a docstring and row counts to the printed message.
- **low, rejected** — no index on `tickets.customer_id`. 24 rows, full scan is free; unrequested complexity for CAP-1's scope.
- **false, rejected** — hardcoded row counts/IDs in tests "silently" couple to seed CSVs. A failing assertion is a loud pytest failure, not silent; `seed/*.csv` is documented read-only, so pinning to its values is intentional.
- **low, rejected** — no validation of malformed/missing CSV rows (non-numeric `open_tickets`, missing headers). Same reasoning as the earlier pass: static, read-only, already-valid fixtures; fix would add guards beyond CAP-1's scope.
- **false, rejected** — `sqlite3.connect(db_path)` would fail if `db_path`'s parent directory doesn't exist. Unreachable: the module default always resolves inside the repo, and no caller (test or CLI) passes a path with a missing parent dir.
- **false, rejected** — CAP-2 is unimplemented and not logged as "not yet built." This story's own frozen Intent explicitly scopes only CAP-1 — an already-surfaced, deliberate choice, not a silent scope cut.
- **rejected (spec-edit)** — Open Question in `SPEC.md` (route↔category pairing) has no named owner/follow-up. Fix would mean editing `SPEC.md`, out of bounds for a code review.
- **false, rejected** — `.env.example` deletion is undertracked. Not part of this diff (`git diff main...HEAD` covers commits only; the deletion is an unrelated, pre-existing uncommitted change).
- **low, rejected** — idempotency test asserts row counts, not full content equality. Content equality is guaranteed by construction (drop+recreate from the same static CSVs every run); a theoretical nitpick, not a real risk.
