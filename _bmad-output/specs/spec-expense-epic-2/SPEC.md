---
id: SPEC-expense-epic-2
companions: ["../spec-expense-claim-reviewer/SPEC.md", "../../planning-artifacts/architecture/architecture-Agentic-Workshop-2026-09-27/ARCHITECTURE-SPINE.md", "../../../cases/expense/POLICY.md"]
sources: ["../../planning-artifacts/prds/prd-Agentic-Workshop-2026-09-27/prd.md"]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Epic 2: Explained & Verified Decisions

*Epic 2 of 2 for Case Expenses (Expense Claim Reviewer). Covers CAP-7 and CAP-8 of `SPEC-expense-claim-reviewer` — capability IDs reused, not renumbered. Builds on Epic 1 (done): `decisions` is fully populated for all 40 claims via `cases/expense/run_agent.py`. Slug is `expense-epic-2` (not `epic-2`) — Saturday's triage agent already owns `_bmad-output/specs/spec-epic-2/`.*

## Why

`cases/expense/BRIEF.md`'s second grading check — "is each explanation clear, and does it cite the right clause?" — and the PRD's counter-metric SM-C1 (must generalize to the unscored 10-claim holdout, verified live at the 3:00 demo) both need this epic. Epic 1 alone proves decisions are correct; it cannot yet prove they're explainable or demonstrate the pass/fail bar a single command checks.

## Capabilities

- **CAP-7**
  - **intent:** Produce a clear, clause-citing explanation for each decision that names the specific fact that triggered it (the amount, the limit, the date gap, the missing receipt), not boilerplate.
  - **success:** The LLM judge rates every explanation as clear and citing the correct clause.

- **CAP-8**
  - **intent:** Score a completed run against `cases/expense/eval/labelled.csv`: per-line-item decision match, cited-clause match, and per-claim reimbursable-total match, where the reimbursable total is the sum of every `approve`-decided item regardless of its $500-gate approval status.
  - **success:** A single command runs the eval and reports pass/fail (or score) per check across the 30 labelled claims.

## Constraints

- `run_agent.py` (Epic 1, done) is extended, not replaced: after `decision_engine.decide_claim` produces `(decision, clause)` for a line item, one LLM call generates the explanation before `record_decision` is called with the same `(line_id, decision, clause)` — the explanation text is never passed to `record_decision` (Spine AD-2: `decisions` stays exactly 3 columns).
- `ChatGoogleGenerativeAI`'s response `.content` is a list of content blocks (e.g. `[{"type": "text", "text": "...", "extras": {...}}]`), not a plain string — explanation-extraction code must handle this shape.
- MLflow traces to the shared `sqlite:///mlflow.db` (root `AGENTS.md`), under an experiment name/tag (e.g. `expense-claim-reviewer`) distinguishing this case's traces from Saturday's triage traces in the same store (Spine AD-7). The explanation text lives in the trace, not in SQLite.
- Model config comes from the root `.env` per `AGENTS.md`: `MODEL` (default `gemini-3.8-flash`) via `ChatGoogleGenerativeAI`, key `GEMINI_API_KEY`; `PROVIDER=groq` switches to `ChatGroq`. Not re-declared per case. Confirmed working: a live call to `gemini-3.8-flash` returns successfully with the keys already present in `.env`.
- `eval/run_eval.py` reads `cases/expense/eval/labelled.csv` directly — labels never move into an MLflow dataset (mirrors Saturday's `eval/labelled_tickets.csv`).
- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/*.csv`, and `eval/labelled.csv` are read-only.

## Non-goals

- Re-deciding or re-validating decision/clause correctness — Epic 1's job, already done and verified (0 mismatches against all 119 labelled line items).
- Building the LLM judge itself — `BRIEF.md`'s live demo grading mechanism is external to this codebase.
- Any interface beyond the existing 3:00 dashboard.

## Success signal

Every decision in `decisions` (all 40 claims) has an associated LLM-generated explanation captured in the MLflow trace, naming the deciding fact and clause. `eval/run_eval.py`, run as a single command, reports decision-match, clause-match, and reimbursable-total-match across the 30 labelled claims at 100%.

## Open Questions

- None — Epic 1's investigation already resolved the two open questions carried in the parent spec (duplicate detection tool surface, same-date tiebreak) and the architecture spine's remaining ones (`get_policy_limits` shape, dashboard schema compatibility) are either resolved by Story 1-1 or still genuinely out of this epic's reach (dashboard schema needs an answer from whoever owns the dashboard, not resolvable here).
