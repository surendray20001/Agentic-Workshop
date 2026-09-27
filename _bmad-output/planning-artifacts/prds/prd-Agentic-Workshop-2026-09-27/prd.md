---
title: Expense Claim Reviewer (MVP)
created: 2026-09-27
updated: 2026-09-27
status: final
---

# PRD: Expense Claim Reviewer (MVP)

## 0. Document Purpose

For whoever builds or reviews this MVP. One agent, one page: builds directly on `brief.md` and `SPEC-expense-claim-reviewer` — this PRD does not repeat their rationale, only the contract to implement against.

## 1. Vision

Finance reviews every expense claim by hand today — a week per cycle, with two reviewers often disagreeing on the same claim — even though the policy behind those decisions is fully deterministic. This MVP is a single agent that applies `POLICY.md` consistently, line item by line item, citing the clause behind every call, so Finance stops re-litigating the same rules from scratch each cycle. Any item over $500 still waits for a person's sign-off before it's paid.

## 2. Target User

### 2.1 Jobs To Be Done

- As a Finance reviewer, decide every line item on a claim consistently and explainably, without re-deriving `POLICY.md`'s 45 clauses by hand each time.
- As the person who signs off on big payouts, see only the items that actually need a human call ($500+), not the whole claim.

### 2.2 Non-Users (v1)

- **Claimants** — the employees whose expense claims are reviewed — are not served in v1. They get no notification, no visibility into their claim's decisions, and no way to check status or contest a rejection. This is a deliberate scope cut inherited from `BRIEF.md` (emailing employees and any new interface are explicitly out of scope), named here so it reads as a decision, not an oversight.

### 2.3 Key User Journeys

- **UJ-1.** A Finance reviewer opens a claim and finds every line item already decided, with the deciding clause cited — they only act on items flagged over $500.
- **UJ-2.** The person who releases payment opens the existing dashboard, sees only the line items pending sign-off at $500+, and approves or holds each one — nothing pays out until they do.

## 3. Glossary

- **Claim** — one expense submission by an employee, made of one or more line items.
- **Line Item** — a single expense line on a claim (date, category, merchant, amount); gets exactly one decision.
- **Clause** — a numbered rule in `POLICY.md` that decides a line item.
- **Decision** — one of `approve`, `flag`, or `reject`, assigned per line item.
- **Reimbursable Total** — the sum of a claim's `approve`-decided line items, regardless of approval-gate status.
- **Approval Gate** — the human sign-off required before any `approve`-decided line item over $500 is paid.
- **Holdout Set** — the 10 claims with no labels, scored live at the demo.

## 4. Features

### 4.1 Expense Claim Review

**Description:** For each of the 40 claims, the agent fetches the claim's line items, the employee's level and city, and the limits that apply, then decides every line item and records it. Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-1: Assemble claim context

The agent can fetch a claim's line items, its employee's level and city, and the limits for that level and city, given only a claim ID.

**Consequences (testable):**
- For all 40 claims, the returned employee, line items, and limits match the seed data exactly.

#### FR-2: Decide each line item

The agent can decide every line item as `approve`, `flag`, or `reject`, applying `POLICY.md`'s clauses in strict first-match order (section 3, then 5.1, then 1.2, then 4.1, then the limits in sections 2 & 6, then 1.3; category default otherwise), aggregating meals (2.1) and ground transport (6.1) per day and treating each hotel (2.2)/flight (2.3) line individually. Realizes UJ-1.

**Consequences (testable):**
- Decision and cited clause match `eval/labelled.csv` for every line item across all 30 labelled claims.

#### FR-3: Detect duplicate line items

The agent can reject the later of two same-employee line items sharing date, merchant, and amount within one claim (5.1), breaking same-date ties on the higher `line_id`.

**Consequences (testable):**
- All 3 duplicate pairs in the seed data resolve to `reject`/5.1 on the higher `line_id`.

**Out of Scope:** Cross-claim duplicate history — not present anywhere in the 40-claim dataset, so not built for MVP.

#### FR-4: Record decisions idempotently

The agent can write each line item's decision and clause to the `decisions` table, overwriting rather than duplicating a prior record for the same line item.

**Consequences (testable):**
- Running the agent twice over the same claim leaves exactly one, unchanged decision row per line item.

#### FR-5: Gate large payouts

The agent can flag any `approve`-decided line item over $500 as pending a person's sign-off, per line item, never per claim total. Realizes UJ-2.

**Consequences (testable):**
- Every such item carries a distinct pending-approval state; none is marked paid without a recorded human approval.

#### FR-6: Explain each decision

The agent can produce a clear explanation per decision that names the specific fact behind it (amount, limit, date gap, missing receipt) and cites the deciding clause.

**Consequences (testable):**
- Every recorded decision includes a non-empty explanation naming the deciding clause. (Explanation *quality* is not an MVP success metric — see §7.)

## 5. Non-Goals (Explicit)

- Actually paying or reimbursing anyone — the agent records the decision; a person releases payment outside this system.
- Emailing employees about their claim decisions.
- Any interface beyond the existing 3:00 dashboard.
- Special-casing the 10-claim holdout set — it runs through the same pipeline as the other 30, just unscored until the demo.

## 6. MVP Scope

### 6.1 In Scope

- One agent, four MCP tools (`get_claim`, `get_employee`, `get_policy_limits`, `record_decision`) over SQLite loaded from `cases/expense/seed/`.
- All 40 claims processed; decisions recorded for every line item.
- Eval run against the 30 labelled claims.

### 6.2 Out of Scope for MVP

- Payout execution (out of scope entirely, not just deferred — see Non-Goals).
- Dashboard UI (already exists elsewhere; not built here).
- A second agent or case (this PRD covers Expense only).

## 7. Success Metrics

`eval/labelled.csv` is the sole success criteria for this MVP — every labelled example must match exactly, per line item:

- **SM-1**: Decision matches `eval/labelled.csv` on 100% of the 30 labelled claims' line items. Validates FR-2, FR-3.
- **SM-2**: Cited clause matches `eval/labelled.csv` on 100% of the 30 labelled claims' line items. Validates FR-2, FR-3.
- **SM-3**: Reimbursable total matches on 100% of the 30 labelled claims. Validates FR-2, FR-4.

**Counter-metrics (do not optimize)**
- **SM-C1**: SM-1/2/3 must not be reached by hard-coding or overfitting to the 30 labelled answers — the same logic has to generalize to the unlabelled 10-claim holdout scored live at the 3:00 demo. Not verifiable by the eval script (no labels exist for the holdout); verified live, at the demo, against real graded outcomes. Counterbalances SM-1, SM-2, SM-3.

**[NOTE FOR PM]** `cases/expense/BRIEF.md` (read-only) also grades explanations with an LLM judge — dropped here as an MVP success metric, but the live demo may still score against it. Revisit before the 3:00 demo if judge quality turns out to matter for grading.

## 8. Open Questions

1. Does `get_policy_limits(level, city)` return all categories at once, or is it called per category? Not blocking — either shape satisfies FR-1.
2. Does the `decisions` table schema match what the existing 3:00 dashboard expects to read? Unresolved — a mismatch would surface only live at the demo.

## 9. Assumptions Index

- §4.1 — The LLM is used for judgment (the decision and the explanation prose); limit math, per-window aggregation, and duplicate detection are computed as precomputed facts via tool calls, not left to the model to compute itself.
