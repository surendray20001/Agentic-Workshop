---
stepsCompleted: [1, 2]
inputDocuments: ['_bmad-output/planning-artifacts/prds/prd-Agentic-Workshop-2026-09-27/prd.md', '_bmad-output/planning-artifacts/architecture/architecture-Agentic-Workshop-2026-09-27/ARCHITECTURE-SPINE.md']
---

# Expense Claim Reviewer - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the Expense Claim Reviewer (Case Expenses), decomposing the requirements from the PRD and Architecture Spine into implementable stories. No UX design contract exists — this MVP adds no new interface.

## Requirements Inventory

### Functional Requirements

FR1: The agent can fetch a claim's line items, its employee's level and city, and the limits for that level and city, given only a claim ID.
FR2: The agent can decide every line item as approve, flag, or reject, applying POLICY.md's clauses in strict first-match order (section 3, then 5.1, then 1.2, then 4.1, then the limits in sections 2 & 6, then 1.3; category default otherwise), aggregating meals (2.1) and ground transport (6.1) per day and treating each hotel (2.2)/flight (2.3) line individually.
FR3: The agent can reject the later of two same-employee line items sharing date, merchant, and amount within one claim (5.1), breaking same-date ties on the higher line_id.
FR4: The agent can write each line item's decision and clause to the decisions table, overwriting rather than duplicating a prior record for the same line item.
FR5: The agent can flag any approve-decided line item over $500 as pending a person's sign-off, per line item, never per claim total.
FR6: The agent can produce a clear explanation per decision that names the specific fact behind it and cites the deciding clause.

### NonFunctional Requirements

No dedicated NFR section exists in the PRD (right-sized for this one-page MVP); the following quality attributes are load-bearing per the Architecture Spine and must be treated as NFRs for story acceptance criteria:

NFR1: Decision-making must be deterministic and reproducible — re-running the agent on the same claim data must always produce the same decision and clause (Spine AD-1, AD-3, AD-12).
NFR2: All currency arithmetic must use exact decimal precision (Python `Decimal`), never floating point, so a line item never lands on the wrong side of POLICY.md's 20%-over threshold due to rounding (Spine AD-8).
NFR3: This work must not modify Saturday's triage agent code, the root `app.db`, or the root `SPEC.md`/epics (Spine AD-6; `AGENTS.md`).

### Additional Requirements

- No starter template needed — brownfield reuse of the repo's existing, already-pinned stack (langchain, langchain-google-genai, langchain-groq, langchain-mcp-adapters, mcp, mlflow, pydantic, python-dotenv; see `pyproject.toml`). No new dependency is introduced.
- Own SQLite database file at `cases/expense/app.db`, separate from Saturday's root `app.db` (Spine AD-6).
- Exactly four MCP tools — `get_claim`, `get_employee`, `get_policy_limits`, `record_decision` — with `decision_engine.py` as a separate, deterministic, LLM-free module that is never registered as a tool (Spine AD-1, AD-5, AD-11).
- `get_policy_limits(level, city)` returns a category-keyed dict of `Decimal` limits (Spine AD-11).
- `decisions` table has exactly the columns `(line_id, decision, clause)`; `record_decision` is an upsert keyed on `line_id`; the natural-language explanation is never persisted to SQLite — it lives in the agent's response content, captured by MLflow tracing (Spine AD-2, AD-3).
- Reimbursable total per claim is a derived read-only query (`SUM(amount)` in `Decimal` over `line_items JOIN decisions` where `decision='approve'`), not a stored column (Spine AD-10).
- The $500+ approval gate is a derived condition (`decision='approve' AND amount > 500`), never a stored state or a fourth decision value (Spine AD-9).
- Full agent runs must truncate `decisions` before starting, so a partial/debug run never leaves eval scoring against a stale mix (Spine AD-12).
- MLflow tracing writes to the shared `sqlite:///mlflow.db`, tagged/experiment-named to distinguish this case's traces from Saturday's (Spine AD-7).
- `cases/expense/INTENT.md` must be written before implementation begins, per root `AGENTS.md`'s Sunday rules.
- `cases/expense/BRIEF.md`, `POLICY.md`, `seed/*.csv`, and `eval/labelled.csv` are read-only inputs, never modified.
- Flagged but explicitly out of scope for these epics: root `pyproject.toml`'s `mcp>=1.9` and `langchain-mcp-adapters>=0.1` pins carry version risk (Spine Deferred) — not to be touched by this case's stories, since the file is shared with Saturday's already-built code.

### UX Design Requirements

None — no UX design contract exists, and no new interface is in scope for this MVP (PRD Non-Goals: "any interface beyond the existing 3:00 dashboard").

### FR Coverage Map

FR1: Epic 1 - assemble claim context (claim, employee, limits)
FR2: Epic 1 - decide each line item per POLICY.md precedence + aggregation
FR3: Epic 1 - detect duplicate line items (5.1)
FR4: Epic 1 - record decisions idempotently
FR5: Epic 1 - $500 gate (derived from FR2+FR4, no separate build)
FR6: Epic 2 - explain each decision, verified by eval

## Epic List

### Epic 1: Claim Decisions Recorded
Every line item across all 40 claims is fetched, decided against POLICY.md (precedence, aggregation, duplicates), and recorded idempotently — with any approved item over $500 visibly distinguishable as pending sign-off. Standalone value: a reviewer can query `decisions` and see every claim resolved correctly, matching the 30 labelled examples.
**FRs covered:** FR1, FR2, FR3, FR4, FR5

### Epic 2: Explained & Verified Decisions
Every recorded decision carries a clear, clause-citing explanation, and the eval script proves the whole pipeline against `eval/labelled.csv` — the actual bar for the 3:00 demo. Builds on Epic 1's recorded decisions; delivers the trust and verification layer.
**FRs covered:** FR6
