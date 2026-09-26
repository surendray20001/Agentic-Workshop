---
id: SPEC-epic-1
companions: [../../../mcp/triage_server.py]
sources: [../../../INTENT.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Epic 1: triage data and schema

## Why

The workshop's later epics — an agent that decides, and an eval that scores those decisions — both need two things to already exist: a database of tickets and customers to query, and a schema that pins down what a valid triage decision looks like. Epic 1 is the foundation those depend on, built before any agent or API key enters the picture.

## Capabilities

- **CAP-1**
  - **intent:** A person can run `uv run python load_seed.py` to load `seed/tickets.csv` and `seed/customers.csv` into a local SQLite file, `app.db`, as tables `tickets` and `customers` with the same columns as the CSVs.
  - **success:** After running the command, `app.db` has a `tickets` table (`ticket_id`, `customer_id`, `created_at`, `text`) and a `customers` table (`customer_id`, `name`, `plan`, `open_tickets`) matching the CSV rows. Running the command a second time leaves the database in the same state (idempotent).

- **CAP-2**
  - **intent:** Every triage decision is validated against a schema before it's accepted; anything that doesn't conform is rejected with a clear error.
  - **success:** A JSON object with `category` in {billing, bug, access, performance, how-to}, `priority` in {P1, P2, P3, P4}, `route` in {billing-team, bug-team, access-team, performance-team, how-to-team}, and a one-sentence rationale validates. A malformed object — missing a field, an enum value outside the allowed set, or an extra/renamed field — is rejected with a clear, specific error rather than passing silently or crashing opaquely.

## Constraints

- Python 3.12 or newer, managed with `uv`; packages are added with `uv add`, never `pip`.
- `seed/tickets.csv` and `seed/customers.csv` are read-only — `load_seed.py` only reads them, never writes.
- No network calls and no API keys anywhere in this epic.
- `mcp/triage_server.py` is read-only and already queries `app.db` for exactly `tickets(ticket_id, customer_id, created_at, text)` and `customers(customer_id, name, plan, open_tickets)`; `load_seed.py` must produce those table and column names precisely, since the server side cannot be adjusted to match.

## Non-goals

- The agent, any MCP tools beyond staying compatible with the existing `mcp/triage_server.py`, the eval harness, and any user interface.

## Success signal

`uv run python load_seed.py` produces an `app.db` that `mcp/triage_server.py`'s `get_ticket` and `get_customer_history` tools can query without modification, and running it again produces the same database. A decision object shaped like `{"category": "billing", "priority": "P2", "route": "billing-team", "rationale": "..."}` validates against the schema; a decision with a bad enum value or a missing field is rejected with a clear error.

## Open Questions

- Should the schema enforce that `route` corresponds to `category` (e.g. `category=billing` implies `route=billing-team`), or are the two enums validated independently? `INTENT.md` lists both value sets but never states a pairing rule.
