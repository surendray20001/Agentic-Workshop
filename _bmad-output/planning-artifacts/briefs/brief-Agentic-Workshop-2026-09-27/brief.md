---
title: Product Brief - Expense Claim Reviewer (Case Expenses)
status: draft
created: 2026-09-27
updated: 2026-09-27
---

# Product Brief: Expense Claim Reviewer

## Executive Summary

Finance currently reviews every expense claim by hand, and two reviewers often reach different decisions on the same claim. This case builds an agent that applies `cases/expense/POLICY.md` consistently, line item by line item, citing the clause behind every call, and leaves any payout over $500 in a person's hands — per line item, not per claim total (POLICY.md 7.1 gates each line, not the claim sum). The spec — problem, tools, and grading — is fully given in `cases/expense/BRIEF.md` and is read-only; this brief exists to lock in *how* it gets built today, ahead of the 3:00 live demo, where the last 10 claims (an unlabelled holdout set) are scored live.

## The Problem

Manual review is slow (a week per cycle) and inconsistent (reviewer-to-reviewer disagreement on identical claims). The policy itself is fully specified and deterministic — every edge case in the data is covered by a numbered clause in `POLICY.md` — so the gap isn't ambiguity in the rules, it's applying 45 clauses across 159 line items, correctly and explainably, every time.

## The Solution

An agent that, per claim: fetches the claim and its line items, looks up the employee, pulls the limits that apply to their level and city, and decides each line item — approve, flag, or reject — citing the deciding clause. Decisions are written to a `decisions` table; nothing gets paid until a person approves any item over $500 (clause 7.1).

**Architecture: reuse Saturday's stack**, per `AGENTS.md`, rather than a bespoke rules engine:
- A LangChain agent (`create_agent`), model from `AGENTS.md` (Gemini via `ChatGoogleGenerativeAI`, Groq as backup/judge), calling MCP tools rather than hand-rolled control flow.
- An MCP server over a SQLite database loaded from `cases/expense/seed/`, exposing the four tools the brief specifies: `get_claim`, `get_employee`, `get_policy_limits`, `record_decision`. **Provisional** — see Open Questions: if duplicate detection (5.1) needs cross-claim history, a fifth tool or a query surface on `get_claim` may be required before this is a settled 4-tool design.
- MLflow tracing on every run, same as Saturday's triage agent, so a bad decision on the holdout set can be root-caused from its trace during the demo.
- Rationale: consistency with the rest of the repo (same patterns the workshop is teaching), and tracing/eval infrastructure comes for free instead of being rebuilt.
- [ASSUMPTION] The LLM is used for judgment (line-by-line decisions and the explanation prose) rather than the entire pipeline being LLM-driven — clause lookup, limit math, and duplicate detection are exact enough that we lean on tool calls returning precomputed facts rather than asking the model to compute a running per-day total itself.

## Success Criteria

Directly from `cases/expense/BRIEF.md`, unchanged:
- **Code checks** against `eval/labelled.csv` (first 30 claims): decision matches per line item, cited clause matches the label, and each claim's reimbursable total (sum of approved items) matches. Reimbursable total = sum of line items decided "approve," regardless of whether the $500 gate has been signed off yet — the gate blocks payout, not the approve/flag/reject decision itself, so pending-approval items still count toward the total.
- **One LLM judge**: is each explanation clear, and does it cite the right clause?
- **Live holdout**: the last 10 claims, ungraded here, scored at the 3:00 demo — the real bar.

## Scope

**In scope (today):**
- MCP server (4 tools) + SQLite load from `cases/expense/seed/`.
- LangChain agent that processes all 40 claims and populates `decisions`.
- Eval script reading `cases/expense/eval/labelled.csv` (per `AGENTS.md`, each case's eval reads its own CSV — labels stay out of any MLflow dataset).
- The $500 human-approval gate before payout (agent records the decision; a person releases payment — no payment execution needed, per Out of Scope below).
- `cases/expense/INTENT.md` written before building, per `AGENTS.md`.

**Out of scope** (per `BRIEF.md`, carried forward as-is): actually paying anyone, emailing employees, any interface beyond the existing 3:00 dashboard.

**Explicitly not touched:** Saturday's triage agent/code (`AGENTS.md`: "Keep Saturday's triage code working; don't change it for Sunday's case"). `POLICY.md`, `BRIEF.md`, `seed/`, and `eval/labelled.csv` inside `cases/expense/` are read-only inputs, not deliverables.

## Risks

1. **Clause precedence (top risk).** `POLICY.md`'s "when more than one clause applies" order — section 3, then 5.1, then 1.2, then 4.1, then limits (sections 2 & 6), then 1.3 — has to be applied as a strict first-match, not independently per clause. A line item that's both over budget *and* missing a receipt must resolve to the limit clause, not 1.3, and both the code checks and the judge will catch this if it's wrong. Note: 1.1 (each line decided on its own) and 1.4 (currency) are standing rules, not competing clauses — they never enter this precedence chain, and shouldn't be slotted into it.
2. **Per-window aggregation — but not uniformly.** Meals (2.1) and ground transport (6.1) aggregate *per day, across line items* within a claim — the running total is the agent's/tool's job to assemble before comparing to the limit. Hotels (2.2) and flights (2.3) do **not** aggregate this way: POLICY.md says each line is already one night or one trip, so each is compared to its limit individually, never summed with other lines. Conflating the two models — e.g. summing multiple hotel-night lines together — misapplies 2.4 for those two categories.
3. **The 1.3 fallback is easy to skip.** 1.3 (no receipt over $25) isn't only a tiebreaker for over-limit items — it's the deciding clause for an item that's *in budget* but missing a receipt. Agent logic that only checks 1.3 after a limit-clause miss, or treats "under limit" as an automatic approve, will silently reimburse unreceipted expenses.
4. **Duplicate detection (5.1)** requires same-employee history — potentially across claims, not just within one — matched on date + merchant + amount. Two failure directions, not one: under-matching (missing a real duplicate because the check doesn't look outside the current claim) and over-matching (scoping the match too broadly and catching two *different* employees who happened to expense the same merchant/date/amount — 5.1 is explicitly scoped to the same employee). Same-date duplicates also need a tiebreaker for "the later one" that `POLICY.md` doesn't define (see Open Questions).
5. **Time pressure.** With the stack reused from Saturday, the main execution risk is wiring (server, agent, load script, eval) inside the time available before 3:00, not any single policy rule.
6. **Re-run idempotency.** If the agent runs twice before 3:00 (e.g. after a bug fix), whether `record_decision` overwrites or appends to `decisions` for the same line item isn't defined yet. Appending would double-count line items in the reimbursable-total check — this needs an answer before the first re-run under time pressure, not after.

## Open Questions

- Does `get_policy_limits(level, city)` return all categories at once (meals, hotel, flight, ground) for that level/city pair, or is it called per category? (Implementation detail for the architecture/spec step, not blocking this brief.)
- **Blocking for the architecture/spec step:** where does duplicate-detection history come from if the duplicate's earlier item is on a *different* claim by the same employee — does `get_claim` need to expose enough to check across claims, or does the agent need a fifth, unlisted tool? This directly determines whether the 4-tool surface in The Solution holds, so it must be resolved before that section is treated as settled, not deferred as a footnote.
- When two duplicate items (same employee, date, merchant, amount) share the *exact same date*, what determines which one is "later" under 5.1 — line item ID order, claim submission timestamp, or claim ID order? `POLICY.md` doesn't specify a tiebreaker.
- Does the `decisions` table schema this build writes match what the 3:00 dashboard expects to read? The dashboard itself is out of scope here, but a schema mismatch discovered live would be the worst-case failure mode — worth a one-line confirmation before the demo.
