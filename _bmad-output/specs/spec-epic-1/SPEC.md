---
id: SPEC-epic-1
companions: ["../../../cases/expense/POLICY.md", "../spec-expense-claim-reviewer/SPEC.md", "../../planning-artifacts/architecture/architecture-Agentic-Workshop-2026-09-27/ARCHITECTURE-SPINE.md"]
sources: ["../../planning-artifacts/prds/prd-Agentic-Workshop-2026-09-27/prd.md"]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Epic 1: Claim Decisions Recorded

*Epic 1 of 2 for Case Expenses (Expense Claim Reviewer). Covers CAP-1 through CAP-6 of `SPEC-expense-claim-reviewer` — capability IDs reused, not renumbered, since they are the same capabilities. CAP-7 (explanation) and CAP-8 (eval scoring) belong to Epic 2, not built here.*

## Why

Finance needs every claim line item decided consistently against `POLICY.md` and recorded, with large payouts visibly gated for a person's sign-off. This epic delivers the deterministic decide-and-record pipeline that Epic 2 (explanation, eval) builds on top of.

## Capabilities

- **CAP-1**
  - **intent:** Given a claim_id, assemble everything needed to decide every line item on it — the employee and line items (`get_claim`), the employee's level and city (`get_employee`), and the limits that apply to them (`get_policy_limits`).
  - **success:** For all 40 claims, the tool chain returns the employee_id, line items, level/city, and limits exactly matching the seed data.

- **CAP-2**
  - **intent:** Decide each line item by applying `POLICY.md`'s clauses in strict first-match order: section 3, then 5.1, then 1.2, then 4.1, then the limits (sections 2 & 6), then 1.3; if none apply, approve under the category's own clause.
  - **success:** Decision and cited clause match `eval/labelled.csv` for every line item across all 30 labelled claims, and the logic generalizes to the unscored 10-claim holdout — no branching on specific claim/line/employee ids.

- **CAP-3**
  - **intent:** Aggregate correctly before comparing to a limit (2.4): sum meals (2.1) and ground transport (6.1) per day across a claim's line items; treat each hotel (2.2) and flight (2.3) line individually — never summed with other lines.
  - **success:** Per-day meal/ground totals and per-line hotel/flight amounts produce the approve/flag/reject split implied by the labels.

- **CAP-4**
  - **intent:** Detect duplicate line items under 5.1 — same employee, date, merchant, and amount — scoped to line items within the current claim. Same-date ties break on `line_id`: higher is "later" and is rejected; lower keeps its normal decision.
  - **success:** All 3 duplicate pairs present in the seed data resolve to `reject`/5.1 on the higher `line_id`, matching the labelled cases exactly.

- **CAP-5**
  - **intent:** Record every line item's decision and clause to the `decisions` table via `record_decision(line_id, decision, clause)`, overwriting rather than appending when a line_id already has a recorded decision.
  - **success:** Running the agent twice over the same claim leaves exactly one decision row per line item, with identical content both times.

- **CAP-6**
  - **intent:** Any line item decided `approve` with amount over $500 must be identifiable as pending a person's sign-off before it is treated as released for payment (7.1) — per line item, never per claim total.
  - **success:** Every approved line item over $500 is correctly identifiable via a derived filter on the recorded decision; no schema change is needed to find them.

## Constraints

- Decision-making is deterministic, not LLM-authored: `decision_engine.py` implements `POLICY.md`'s precedence order in plain code with no branching on specific claim/line/employee ids. The LLM (Epic 2's concern) never picks the decision or clause.
- `decisions` has exactly the columns `(line_id, decision, clause)`; `record_decision` is an upsert keyed on `line_id`.
- Exactly four MCP tools — `get_claim`, `get_employee`, `get_policy_limits`, `record_decision`; `decision_engine.py` is a plain internal module, never a fifth tool.
- `get_policy_limits(level, city)` returns `{category: Decimal(limit_cad)}`.
- All currency arithmetic uses `Decimal`, never `float`, including across the MCP JSON-RPC wire (serialized as strings).
- This case's SQLite file is `cases/expense/app.db`, separate from Saturday's root `app.db`; nothing here imports from or writes to root `mcp/`, `run_agent.py`, or root `app.db`.
- Full agent runs truncate `decisions` before starting over all 40 claims; a partial/debug run is not eval-safe.
- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/*.csv`, and `eval/labelled.csv` are read-only.
- `cases/expense/INTENT.md` is written before implementation begins, per root `AGENTS.md`'s Sunday rules.

## Non-goals

- Explanation text (CAP-7) and eval scoring (CAP-8) — Epic 2's scope, not built here.
- Actually paying or reimbursing anyone.
- Emailing employees about their claim decisions.
- Any interface beyond the existing 3:00 dashboard.

## Success signal

For all 40 claims, every recorded decision `(line_id, decision, clause)` correctly resolves `POLICY.md`. Against the 30 labelled claims, decision and cited clause match `eval/labelled.csv` exactly on every line item — checkable by direct comparison even before Epic 2's formal eval script exists. Every duplicate pair and every aggregation case resolves correctly. Approve-decisions over $500 are correctly identifiable via the derived filter (no stored gate state needed).

## Open Questions

- Does the `decisions` schema match what the existing 3:00 dashboard expects to read? Not resolvable from this epic's spec alone — carried from the parent spec and PRD.
