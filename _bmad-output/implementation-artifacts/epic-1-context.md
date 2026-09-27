# Epic 1 Context: Claim Decisions Recorded

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Every line item across all 40 expense claims must be fetched, decided against `POLICY.md`, and recorded idempotently in `decisions` — so a reviewer can query `decisions` and see every claim resolved correctly, matching the 30 labelled examples, with any approved item over $500 visibly distinguishable as pending a person's sign-off. This is the deterministic decide-and-record pipeline that the explanation and eval layer (Epic 2) builds on top of.

## Stories

- Story 1-1: MCP server - claim context tools
- Story 1-2: Deterministic policy decision engine
- Story 1-3: Record decisions idempotently, with the $500 gate
- Story 1-4: Orchestrate a full run over all 40 claims

## Requirements & Constraints

- Given only a claim ID, assemble everything needed to decide it: line items, the employee's level and city, and the limits that apply — matching seed data exactly for all 40 claims.
- Decide every line item as `approve`, `flag`, or `reject` via `POLICY.md`'s clauses in strict first-match order: section 3, then 5.1, then 1.2, then 4.1, then the limits (sections 2 & 6), then 1.3; category default if none match. A line item tripping both a limit and a missing-receipt condition must resolve to the limit clause, not 1.3 — this is strict first-match, not independent per-clause checks. 1.3 is also the deciding clause for in-budget items missing a receipt, not only a post-limit tiebreaker.
- Aggregate before comparing to a limit: sum meals (2.1) and ground transport (6.1) per day across a claim's line items; treat each hotel (2.2) and flight (2.3) line individually, never summed with other lines.
- Detect duplicates (5.1): same employee, date, merchant, and amount, scoped to line items within the current claim (a full-dataset scan found zero cross-claim duplicates, so single-claim scope is an accepted approximation). Same-date ties break on `line_id`: higher is "later" and is rejected.
- Record every line item's decision and clause via an upsert keyed on `line_id`; re-running the agent must leave exactly one, unchanged decision row per line item.
- Any `approve`-decided line item over $500 must be identifiable as pending sign-off, per line item never per claim total, via a derived filter — not a stored state or new decision value.
- Decision and cited clause must match `eval/labelled.csv` exactly across all 30 labelled claims, and generalize correctly to the unscored 10-claim holdout (no branching on specific claim/line/employee IDs).
- All 3 seed duplicate pairs must resolve to `reject`/5.1 on the higher `line_id`.
- Decision-making must be deterministic and reproducible; all currency arithmetic uses exact decimal precision, never float, so rounding never flips a line item across a percentage threshold.
- Must not modify Saturday's triage agent code, the root `app.db`, or the root `SPEC.md`/epics.

## Technical Decisions

- Design paradigm: "Deterministic Policy Core with an LLM Narrator." `decision_engine.py` is pure, dependency-free code (no dependency on the MCP server, the agent, SQLite, or the LLM) implementing precedence, aggregation, and duplicate detection — unit-testable against `eval/labelled.csv` with no model in the loop. The LLM never picks a decision or clause (Epic 2's concern only).
- Exactly four MCP tools: `get_claim`, `get_employee`, `get_policy_limits`, `record_decision`. `decision_engine.py` is a plain internal module, never a fifth tool.
- `get_policy_limits(level, city)` returns `{category: Decimal(limit_cad)}` for all four categories; `decision_engine.py` indexes by the category name exactly as in `limits.csv`.
- `decisions` has exactly the columns `(line_id, decision, clause)`. `record_decision` is `INSERT ... ON CONFLICT(line_id) DO UPDATE`, `line_id` as primary key. Explanations are never persisted to SQLite (Epic 2 captures them via MLflow trace).
- The $500+ approval gate is a derived condition (`decision='approve' AND amount > 500`) — never a stored column or fourth decision value.
- Amounts are parsed as `Decimal` at the SQLite boundary; all sums/comparisons use `Decimal`. Across the MCP JSON-RPC wire, amount/limit fields are strings and must be parsed to `Decimal` immediately on receipt — never native `float`.
- IDs (`claim_id`, `line_id`, `employee_id`) are opaque strings passed through verbatim. Dates are ISO `YYYY-MM-DD`.
- This case's SQLite file is `cases/expense/app.db`, separate from Saturday's root `app.db`; nothing here imports from or writes to root `mcp/`, `run_agent.py`, or root `app.db`. `load_seed.py` must be idempotent.
- A full run over all 40 claims must truncate `decisions` before starting, so a partial/debug run never leaves eval scoring against a stale mix.
- Model/provider config comes from the root `.env` (`MODEL`, `GEMINI_API_KEY`, `PROVIDER`, `JUDGE_MODEL`, `GROQ_API_KEY`) — not re-declared per case.
- `line_id` is a given seed-data field (not assigned by `load_seed.py`); its ascending order was empirically verified against all 3 observed duplicate pairs before adoption as the same-date tiebreak.
- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/*.csv`, and `eval/labelled.csv` are read-only. `cases/expense/INTENT.md` must be written before implementation begins.

## Cross-Story Dependencies

- Story 1-1 (MCP claim-context tools + seed load) provides the real data every later story builds and tests against.
- Story 1-2 (decision engine) is unit-tested against `eval/labelled.csv` using Story 1-1's real seed data, but has no code dependency on the MCP server.
- Story 1-3 (record + $500 gate) depends on Story 1-2's `(decision, clause)` output to know what to upsert, and reuses Story 1-1's database.
- Story 1-4 (full 40-claim orchestration) wires Stories 1-1 through 1-3 together and owns the truncate-before-run behavior.
- Epic 2 (explanation + eval) builds on this epic's recorded decisions and can't start meaningfully until `decisions` is populated correctly.
