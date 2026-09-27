# Expense claim reviewer: rules for coding agents

## What this is

An agent that reviews expense claims against `POLICY.md`, line item by line item, citing the clause behind every decision. Finance currently does this by hand — a week per cycle, with reviewers disagreeing on identical claims — even though the policy is fully deterministic. This agent applies it consistently: for each claim, it fetches the employee and line items, looks up the limits that apply, decides every line item (approve, flag or reject) with a cited clause, and records it. Any approved item over $500 waits for a person's sign-off before payout.

Built per `_bmad-output/specs/spec-expense-claim-reviewer/SPEC.md`; that spec (plus `POLICY.md` as its companion) is the canonical contract — read it before changing behavior here.

## Commands

- Load the data into `cases/expense/app.db`: `uv run python cases/expense/load_seed.py`
- Run the agent on one claim: `uv run python cases/expense/run_agent.py <claim_id>` (e.g. `CL-2001`)
- Run the eval: `uv run python cases/expense/eval/run_eval.py`
- MLflow UI: `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db`

## Rules

- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/` and `eval/labelled.csv` are read-only.
- The MCP server exposes exactly four tools: `get_claim`, `get_employee`, `get_policy_limits`, `record_decision`. No fifth tool — duplicate detection (5.1) is scoped to line items within the current claim; the seed data has zero cross-claim duplicates.
- Apply `POLICY.md`'s clauses in strict first-match order: section 3, then 5.1, then 1.2, then 4.1, then the limits (sections 2 & 6), then 1.3; otherwise approve under the category's own clause. 1.1 and 1.4 are standing rules, not part of this chain.
- Meals (2.1) and ground transport (6.1) aggregate per day across a claim's line items; hotels (2.2) and flights (2.3) do not — each line is already one night or one trip and is judged on its own.
- Same-date 5.1 duplicates: the higher `line_id` is "later" and gets rejected; the lower keeps its normal decision.
- `record_decision` overwrites, not appends — re-running the agent must never double-count a line item.
- Any `approve` decision over $500 is gated behind a person's sign-off, per line item, not per claim total. The agent records the decision; it never releases payment.
- The eval reads `cases/expense/eval/labelled.csv` directly — never move the labels into an MLflow dataset.
- Don't touch Saturday's triage agent code or the root `SPEC.md`/epics for this work.
- Out of scope: actually paying anyone, emailing employees, and any interface beyond the existing 3:00 dashboard.
