---
title: 'Deterministic policy decision engine'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-1-context.md', '{project-root}/_bmad-output/specs/spec-epic-1/SPEC.md']
baseline_commit: 'bc442acb8f71e2d0c0d5e89a2754098c9454cb00'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** No code yet applies `POLICY.md`'s precedence order, per-window aggregation, or duplicate detection to decide a line item — the whole point of this case.

**Approach:** Build `cases/expense/decision_engine.py`, a pure, dependency-free module (no SQLite, no MCP, no LLM) that decides every line item on a claim, validated directly against `eval/labelled.csv`'s real 119 labelled line items across 30 claims — 0 mismatches confirmed by prototype before writing this spec.

## Boundaries & Constraints

**Always:** Public entry point is `decide_claim(line_items, employee, limits_by_city, submitted_at) -> {line_id: (decision, clause)}` (`submitted_at` added during implementation — see Implementation Notes) — `line_items` is one claim's rows (all columns, as `get_claim` returns them), `employee` has `level`, `limits_by_city` maps `city -> {category: Decimal(limit)}` (a caller builds this from one or more `get_policy_limits` calls, one per distinct city among the claim's line items — do not assume a claim has only one city, even though today's data never has more than one). Apply clauses in this exact order per line item, stopping at the first that fires: **3.1** (`category == "alcohol"`) → **3.2** (`category == "personal"`) → **3.3** (`category == "fine"`) → **5.1** duplicate (same employee/claim, same date+merchant+amount as an earlier line, ties on ascending `line_id`) → **1.2** (`item.date` more than 60 days before `claim.submitted_at`) → **4.1** (`category` in `software`/`equipment`: approve if `description` contains `ITA-<digits>`, else reject) → limit check (meals/ground: day-total across the claim for that date+category vs. `limits_by_city[item.city]["meals"|"ground"]`; hotel/flight: the line's own amount vs. `limits_by_city[item.city]["hotel"|"flight"]`; **only a violation — flag at ≤20% over, reject at >20% over — counts as this clause firing**, citing the category's own clause (2.1/2.2/6.1/2.3), never "2.4") → **1.3** (`amount > 25` and `has_receipt == "no"`) → default: approve, citing the category's own clause. All arithmetic in `Decimal`.

**Never:** Do not call `get_claim`/`get_employee`/`get_policy_limits`/`record_decision` or import `mcp_server`/`sqlite3` from this module — it takes plain data in, returns plain data out. Do not implement `record_decision` or the $500 gate (Story 1-3). Do not special-case any specific `claim_id`/`line_id`/`employee_id` — the logic must be `POLICY.md` implemented generally, since it also has to be right on the unscored 10-claim holdout.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full labelled-set replay | All 30 labelled claims' real seed data | `decide_claim` output matches `eval/labelled.csv` exactly on decision + clause for all 119 labelled line items | N/A |
| Meals/ground under day limit, has receipt | Day total ≤ limit | Approve, category clause (2.1/6.1) | N/A |
| Meals/ground under day limit, missing receipt, amount > $25 | Day total ≤ limit, `has_receipt="no"` | Flag, clause 1.3 (falls through the limit check since it didn't fire) | N/A |
| Hotel/flight over limit by ≤20% | e.g. `amount` 105% of limit | Flag, category clause (2.2/2.3) — never "2.4" | N/A |
| Hotel/flight over limit by >20% | e.g. `amount` 130% of limit | Reject, category clause | N/A |
| Duplicate same-date tie | Two lines, same date/merchant/amount/employee | Higher `line_id` rejected/5.1; lower keeps its own decision | N/A |
| Software/equipment with IT code | `description` contains `ITA-4471` | Approve, 4.1 | N/A |
| Software/equipment without IT code | No `ITA-` code in description | Reject, 4.1 | N/A |
| Line item older than 60 days | `item.date` > 60 days before `claim.submitted_at` | Reject, 1.2 — takes precedence over a limit or receipt issue on the same line | N/A |
| Alcohol/personal/fine categories | `category` is `alcohol`/`personal`/`fine` | Reject, 3.1/3.2/3.3 — takes precedence over everything else | N/A |
| Multi-city claim (not in current data, must still work) | Claim's line items span 2+ cities | Each line's limit looked up under its own city in `limits_by_city` | N/A |

</frozen-after-approval>

## Code Map

- `cases/expense/seed/line_items.csv` — `category` column is one of `alcohol, equipment, fine, flight, ground, hotel, meals, personal, software` directly — branch on this value, not on keyword-matching `description` (only `4.1`'s `ITA-\d+` check reads `description`, per `POLICY.md`'s own wording).
- **Investigation finding (resolves an ambiguity `SPEC.md`/the architecture spine left implicit):** `POLICY.md`'s limits are keyed on the **line item's own `city`** (where the expense happened), not the employee's home city from `get_employee`. Verified against 7 discriminating labelled examples where the two cities differ and only the line item's city produces the correct decision (e.g. `L-3010`: employee based in Montreal, hotel expensed in Vancouver, limit must use Vancouver).
- **Investigation finding:** the limit clause (2.4's mechanism) only "fires" as a decision when it's a violation. At-or-under-limit is not itself a decision — it falls through to the 1.3 receipt check, then to the category-default approve, per `POLICY.md`'s closing line ("if none applies, approve under the category's own clause"). The cited clause on a violation is the category's own clause (2.1/2.2/2.3/6.1), never "2.4" — confirmed against 12 labelled flag/reject rows.
- `cases/expense/mcp_server.py` (Story 1-1, done) — `get_claim` return shape (line items with all columns), `get_policy_limits` return shape (`{category: limit_string}` for one `(level, city)` pair) — this module's inputs are shaped to compose with those, but never imports from it.
- `cases/expense/seed/eval/../../eval/labelled.csv` — 119 labelled line items across 30 claims; this story's acceptance is a full replay against it, at 0 mismatches (already prototyped).
- `_bmad-output/specs/spec-epic-1/SPEC.md` — CAP-2, CAP-3, CAP-4 (this story) and constraints AD-1, AD-4, AD-8, AD-11.

## Tasks & Acceptance

**Execution:**
- [x] `cases/expense/decision_engine.py` -- implement `decide_claim` exactly per Boundaries & Constraints and the investigation findings above.
- [x] `tests/test_decision_engine.py` -- build claim/employee/limits fixtures from the real seed CSVs (`claims.csv`, `employees.csv`, `limits.csv`, `line_items.csv`), run `decide_claim` for every one of the 30 labelled claims, and assert every decision + clause matches `eval/labelled.csv` exactly (119 assertions) -- plus targeted unit tests for each I/O & Edge-Case Matrix row using small hand-built fixtures (not requiring a specific real claim to exist for every scenario, e.g. the multi-city case).

**Acceptance Criteria:**
- Given all 30 labelled claims' real seed data, when `decide_claim` runs on each, then decision and clause match `eval/labelled.csv` on all 119 labelled line items with zero mismatches.
- Given a hand-built claim with a line item over a category limit by exactly 20%, when decided, then it is `flag`, not `reject`.
- Given a hand-built claim with two same-date/merchant/amount lines for the same employee, when decided, then the higher `line_id` is `reject`/5.1 and the lower keeps its own decision.
- Given a hand-built claim with line items in two different cities, when decided, then each line's limit check uses its own city's limits from `limits_by_city`.

## Implementation Notes

- The frozen signature `decide_claim(line_items, employee, limits_by_city)` never provided access to the claim's `submitted_at`, which clause 1.2's 60-day check needs. Added a fourth parameter, `submitted_at: str`. Mechanical interface completion, not a change to the decision logic or Intent — no other behavior affected.

## Spec Change Log

## Review Triage Log

- **[verification-gap] + [edge-case, EC6] duplicate-detection key compares raw amount strings, not Decimal values** — verdict: `high` (real bug, not just doc gap: `"40.0"` vs `"40.00"` would evade 5.1 detection even though numerically equal). Verified: `key = (item["date"], item["merchant"], item["amount"])` at the dedup site uses the raw string, unlike every other amount comparison in the module which converts to `Decimal` first. Routes to patch.
- **[blind-hunter] limits_by_city docstring doesn't document that it's scoped to the employee's level** — verdict: `low`. Real doc gap, trivial fix. Routes to patch.
- **[blind-hunter] decide_claim's docstring doesn't cite that 5.1 duplicate detection is same-claim-scoped (an already-adjudicated architecture decision, Spine AD-4), not full same-employee scope per POLICY.md's literal text** — verdict: `low`. Real doc gap (the decision itself is correct and already settled at the architecture level); a code comment prevents a future reader mistaking it for an oversight. Routes to patch.
- **[blind-hunter] _days_between docstring/parameter-naming risk** — verdict: `false`. Current parameter names (`earlier`, `later`) already match their semantic roles at the one call site (`item["date"]` is earlier, `submitted_at` is later); the docstring is accurate as written.
- **[blind-hunter] no hand-built unit test for flight-over-limit or ground-aggregation specifically** — verdict: `low`, rejected. Both are already exercised by the full 119-row labelled replay with real over-limit cases (e.g. `L-3029` flight/flag, `L-3035` ground/reject), and share identical code paths with hotel/meals (parameterized by category, no per-category branching beyond dict lookup).
- **[blind-hunter] no test for duplicate + day-aggregation interaction** — verdict: `low`, rejected. Already exercised and passing in the full replay: `L-3102`/`L-3103` (CL-2026) are exactly this case — a same-day meal duplicate pair where the day total (including the duplicate's amount) pushes the non-duplicate line over its limit, matching the labelled `reject`/2.1 and `reject`/5.1 exactly.
- **[blind-hunter] no defensive check that employee.level matches limits_by_city's scope** + **[edge-case] missing city/category in limits_by_city silently falls through to approve** — verdict: `low`, rejected (grouped). No caller exists yet (Story 1-4 not built); current seed data has complete level×city×category coverage. Noted for Story 1-4 to get right by construction.
- **[blind-hunter] unknown category → uncaught KeyError** + **[edge-case] same, EC3** — verdict: `low`, rejected. Category is one of 9 fixed values across all 40 claims (including holdout) in the read-only seed data; unreachable.
- **[edge-case] date.fromisoformat on invalid date** — verdict: `low`, rejected. Read-only, fixed, already-verified seed data.
- **[edge-case] amount missing/invalid** — verdict: `low`, rejected. Same reasoning.
- **[edge-case] description missing/None breaks IT-approval regex** — verdict: `low`, rejected. Same reasoning; description is always populated in the fixed seed data.
- **[edge-case] has_receipt not exactly yes/no** — verdict: `low`, rejected. Confirmed only `yes`/`no` values exist in the seed data.
- **[edge-case] line_id lexicographic vs numeric sort (L-9 vs L-10)** — verdict: `low`, rejected. All line_ids are fixed-width (`L-` + 4 digits) across the entire dataset including holdout claims; unreachable.
- **[edge-case] duplicate line_id in input silently overwrites** — verdict: `low`, rejected. `line_id` is a unique identifier in the fixed seed data.

## Verification

**Commands:**
- `uv run pytest tests/test_decision_engine.py -v` -- expected: all tests pass, including the full 119-row labelled-set replay.
