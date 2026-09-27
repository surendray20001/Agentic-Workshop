---
id: SPEC-expense-claim-reviewer
companions: ["../../../cases/expense/POLICY.md"]
sources: ["../../../cases/expense/BRIEF.md", "../../planning-artifacts/briefs/brief-Agentic-Workshop-2026-09-27/brief.md"]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Expense Claim Reviewer

## Why

Finance reviews every expense claim by hand — a week per cycle, with two reviewers often reaching different answers on the same claim — even though the policy itself is fully deterministic: `POLICY.md` covers every edge case in the data with 45 numbered clauses. The gap is consistent, explainable application, not ambiguity. Build an agent that applies the policy the same way every time, cites the deciding clause, and defers any payout over $500 to a person. Timeboxed to today's 3:00 live demo, where a 10-claim holdout set is scored live.

## Capabilities

- **CAP-1**
  - **intent:** Given a claim_id, assemble everything needed to decide every line item on it — the employee and line items (`get_claim`), the employee's level and city (`get_employee`), and the limits that apply to them (`get_policy_limits`).
  - **success:** For all 40 claims, the tool chain returns the employee_id, line items, level/city, and limits exactly matching the seed data.

- **CAP-2**
  - **intent:** Decide each line item by applying `POLICY.md`'s clauses in strict first-match order: section 3, then 5.1, then 1.2, then 4.1, then the limits (sections 2 & 6), then 1.3; if none apply, approve under the category's own clause. 1.1 and 1.4 are standing rules, not part of this chain.
  - **success:** Decision and cited clause match `eval/labelled.csv` for every line item across all 30 labelled claims.

- **CAP-3**
  - **intent:** Aggregate correctly before comparing to a limit (2.4): sum meals (2.1) and ground transport (6.1) per day across a claim's line items; treat each hotel (2.2) and flight (2.3) line individually — never summed with other lines, since each line already represents one night or one trip.
  - **success:** Per-day meal/ground totals and per-line hotel/flight amounts produce the approve/flag/reject split implied by the labels (at/under limit approves, ≤20% over flags, >20% over rejects).

- **CAP-4**
  - **intent:** Detect duplicate line items under 5.1 — same employee, same date, merchant, and amount — scoped to line items within the current claim. When two duplicates share the same date, the one with the higher `line_id` is "later" and is rejected; the lower `line_id` keeps its normal decision.
  - **success:** All 3 duplicate pairs present in the seed data resolve to `reject`/5.1 on the higher `line_id`, matching the labelled cases exactly.

- **CAP-5**
  - **intent:** Record every line item's decision and clause to the `decisions` table via `record_decision(line_id, decision, clause)`, overwriting rather than appending when a line_id already has a recorded decision.
  - **success:** Running the agent twice over the same claim leaves exactly one decision row per line item, with identical content both times.

- **CAP-6**
  - **intent:** Gate any line item decided `approve` with amount over $500 behind a person's sign-off before it is treated as released for payment (7.1) — the gate applies per line item, never per claim total.
  - **success:** Every approved line item over $500 carries a distinct pending-approval state in the recorded decision; none is marked paid without a recorded human approval.

- **CAP-7**
  - **intent:** Produce a clear, clause-citing explanation for each decision that names the specific fact that triggered it (the amount, the limit, the date gap, the missing receipt), not boilerplate.
  - **success:** The LLM judge rates every explanation as clear and citing the correct clause.

- **CAP-8**
  - **intent:** Score a completed run against `cases/expense/eval/labelled.csv`: per-line-item decision match, cited-clause match, and per-claim reimbursable total match, where the reimbursable total is the sum of every `approve`-decided item regardless of its $500-gate approval status.
  - **success:** A single command runs the eval and reports pass/fail (or score) per check across the 30 labelled claims.

## Constraints

- Architecture reuses Saturday's stack: a LangChain agent (`create_agent`) calling MCP tools — not hand-rolled control flow — over a SQLite database loaded from `cases/expense/seed/`, traced in MLflow (`sqlite:///mlflow.db`). Model per root `AGENTS.md`: Gemini via `ChatGoogleGenerativeAI` (default), Groq as backup/judge.
- The MCP server exposes exactly four tools — `get_claim`, `get_employee`, `get_policy_limits`, `record_decision` — no fifth tool. (Resolved: a scan of all 159 line items across all 40 claims found zero cross-claim duplicates; every observed 5.1 case is within a single claim, so `get_claim`'s own line items are sufficient.)
- `cases/expense/POLICY.md`, `BRIEF.md`, `seed/*.csv`, and `eval/labelled.csv` are read-only; nothing in this build modifies them.
- The eval reads `cases/expense/eval/labelled.csv` directly; labels never move into an MLflow dataset (mirrors Saturday's `eval/labelled_tickets.csv`).
- Saturday's triage agent code and the root `SPEC.md`/epics are untouched by this work.
- `cases/expense/INTENT.md` is written before implementation begins, per `AGENTS.md`'s Sunday rules.

## Non-goals

- Actually paying or reimbursing anyone — the agent records the decision; a person releases payment outside this system.
- Emailing employees about their claim decisions.
- Any interface beyond the existing 3:00 dashboard.
- Special-casing the 10-claim holdout set — it runs through the same pipeline as the other 30, just unscored until the live demo.

## Success signal

On the 30 labelled claims, every line item's decision and cited clause match `eval/labelled.csv`, and every claim's reimbursable total matches, per the eval script; the LLM judge rates every explanation clear and correctly cited. The full pipeline — load seed, agent decides all 40 claims, decisions recorded, eval reports a score — runs end-to-end before 3:00, at which point the 10-claim holdout is scored live through the same pipeline.

## Assumptions

- The LLM is used for judgment — the line-by-line decision and the explanation prose — while limit math, per-window aggregation, and duplicate detection are computed as precomputed facts (via tool calls / deterministic code), not left to the model to compute itself.

## Open Questions

- Does `get_policy_limits(level, city)` return all categories (meals, hotel, flight, ground) at once, or is it called per category? Not blocking — either shape satisfies CAP-1; left to the architecture/implementation step.
- Does the `decisions` table schema this build writes match what the existing 3:00 dashboard expects to read? The dashboard is out of scope to build here, but a schema mismatch would surface only live at the demo.
