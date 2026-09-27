# Intent: Story 1-1 — MCP server: claim context tools

Building the read-only data layer for Case Expenses, per
`_bmad-output/specs/spec-epic-1/stories/1-1-mcp-server-claim-context-tools.md`.

- `load_seed.py` loads `cases/expense/seed/*.csv` into `cases/expense/app.db`
  (tables `claims`, `employees`, `limits`, `line_items`), drop-and-recreate so
  reruns are idempotent. Isolated from the root `app.db`.
- `mcp_server.py` exposes three read-only MCP tools — `get_claim`,
  `get_employee`, `get_policy_limits` — following the shape of
  `mcp/triage_server.py` (FastMCP, `sqlite3.Row`-based `_query`, `ValueError`
  for not-found, `FileNotFoundError` if the db hasn't been loaded).
- Amounts/limits cross the wire as decimal-safe strings, never native float.
- No decision logic, no `record_decision`, no $500 gate — that's Stories 1-2
  and 1-3. Exactly three tools in this story (the fourth, `record_decision`,
  comes later).
- Tests live at `tests/test_expense_mcp_server.py` per repo `pyproject.toml`
  `testpaths`.
