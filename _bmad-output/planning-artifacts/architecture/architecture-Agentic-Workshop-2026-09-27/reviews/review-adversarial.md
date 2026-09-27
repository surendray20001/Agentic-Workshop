---
name: 'Adversarial Review — Expense Claim Reviewer Architecture Spine'
type: architecture-review
target: ARCHITECTURE-SPINE.md (2026-09-27)
method: construct two literal-compliant builders one level below the spine; find pairs that are individually AD-compliant but mutually incompatible
status: draft
created: '2026-09-27'
---

# Adversarial Review — two builders, one AD, no interop

Method: for each finding, Builder A and Builder B each satisfy every AD's Rule text as written.
Neither violates a Rule. They still can't be dropped into the same repo and work together.

---

## Finding 1 — `get_policy_limits` return shape: per-category dict vs. per-category rows

**Pair:** MCP-server developer vs. decision-engine developer, built from the spine without talking to each other.

- **Builder A (mcp_server.py owner)** reads AD-5's Rule ("the MCP server exposes only `get_claim`, `get_employee`, `get_policy_limits`, `record_decision`") and the Deferred note ("Whether `get_policy_limits(level, city)` returns all categories at once or per-category ... left to implementation"). They pick the natural MCP-tool shape: a single JSON object keyed by category, `{"meals": 60, "hotel": 180, "flight": 900, "ground": 40}`, one row per `(level, city)` collapsed into one dict — clean, one round trip.
- **Builder B (decision_engine.py owner)**, working only from `POLICY.md` §2 and `limits.csv`'s actual row shape (`level,city,category,limit_cad`), writes `decide_line_item(line_item, employee, limits, claim_line_items)` assuming `limits` is a **list of row-like records** (`[{"category": "meals", "limit_cad": Decimal("60")}, ...]`), because that's what `get_policy_limits` would return if it "returns limits" (plural) the way `get_claim` returns "line items" (plural, a list).

Both builders satisfy AD-5 (still exactly 4 tools, `decision_engine.py` still not registered as a tool) and AD-1 (decision-making is still deterministic code, not LLM-authored). Neither violates a Rule. But `decision_engine.decide_line_item(..., limits, ...)` breaks at the boundary: one side hands a dict, the other expects a list, and there's no test that catches it until integration, because AD-1's unit tests (against `eval/labelled.csv`) are written by whichever of the two developers wrote `decision_engine.py`, using their own assumed shape — they pass in isolation.

- **Ambiguous AD:** AD-5's Rule fixes tool *names and count*, not tool *return shapes*. The Deferred section explicitly defers the shape question and asserts "either shape works with `decision_engine.py`" — but that claim is only true if one developer builds both sides. It is false as a contract between two independent developers.
- **Tightening:** Promote the deferred item out of "low fork-risk, left to implementation" into an AD. Add a Rule to AD-5 (or a new AD-5a): "`get_policy_limits(level, city)` returns a list of `{category, limit_cad}` records, one per category, matching `limits.csv`'s grain; `decision_engine.py`'s `limits` parameter has this exact shape." Pin the interface at the module boundary the two builders actually cross, not just at the tool-count level.

---

## Finding 2 — Currency at the MCP boundary: `Decimal`-typed vs. Decimal-parsed-later

**Pair:** MCP-server developer vs. LangChain-agent developer.

- **Builder A (mcp_server.py owner)** reads AD-8's Rule: "amounts are parsed as `decimal.Decimal` **at the SQLite boundary**." They take this literally as *their* responsibility, since `mcp_server.py` is the thing that touches SQLite. `get_claim` therefore returns line items with `amount` already a `Decimal` object inside the returned Python structure.
- **Builder B (run_agent.py / MCP client owner)** knows MCP tool results cross a JSON-RPC wire (per the `mcp` package's transport) and JSON has no `Decimal` type. They reason from AD-8's same sentence — "parsed as Decimal at the SQLite boundary" — that *their* side, receiving JSON over MCP, is the true SQLite-adjacent boundary for their process, so they parse `amount` strings back into `Decimal` themselves after deserializing the tool response, expecting to receive **strings** (`"546.57"`) from `get_claim`, not floats or pre-boxed Decimals.

Builder A's implementation, tested in-process (calling `mcp_server.py` functions directly in a unit test, never through the real MCP JSON transport), never notices that `Decimal` isn't JSON-serializable — the test passes because it skips serialization. Only a real end-to-end MCP round trip reveals that the value silently became a `float` (if using `json.dumps(default=float)`) or raised a `TypeError` (if not), either of which reintroduces exactly the float-rounding risk AD-8 exists to prevent, or breaks the pipe outright.

- **Ambiguous AD:** AD-8's Rule names *a* boundary ("the SQLite boundary") without naming *which process* is on the SQLite side of the MCP wire, and without saying what wire-format money takes across MCP (a protocol that only carries JSON-serializable types). "Decimal, never float" is unenforceable across a JSON-RPC hop as currently worded — one side must own the string↔Decimal conversion, and the Rule doesn't say who.
- **Tightening:** Add to AD-8: "MCP tool responses carry amounts as decimal **strings** (e.g. `"546.57"`), never JSON numbers. `mcp_server.py` converts `Decimal → str` when building a tool response; `run_agent.py` (or its MCP client wrapper) converts `str → Decimal` immediately on receipt, before any arithmetic. `decision_engine.py` never receives anything but `Decimal`." This also forces AD-1's unit tests to exercise the real serialization path, not just in-process calls.

---

## Finding 3 — Duplicate detection tie-break: "ascending `line_id`" assumes a shape `line_id` doesn't guarantee

**Pair:** load-script developer vs. decision-engine developer.

- **Builder B (decision_engine.py owner)** implements AD-4's Rule verbatim: "Same-date 5.1 ties break on ascending `line_id` (lower kept, higher rejected)." Seeing `line_id` values like `L-3001`, `L-3002`, they implement "ascending" as **lexicographic string comparison** (`"L-3001" < "L-3002"`), which happens to agree with numeric order in the sample data and requires no assumption about `line_id` being numeric — consistent with the Consistency Convention that IDs are "opaque strings, passed through verbatim — never parsed or reformatted."
- **Builder A (load_seed.py owner)**, idempotently loading `line_items.csv` (AD-6's convention: idempotent, run-twice-same-result), does not guarantee CSV row order is preserved as `line_id` lexicographic order after re-runs, upserts, or a future seed file with, say, `L-299` and `L-3001` in the same claim (where lexicographic order disagrees with numeric/temporal order: `"L-299" > "L-3001"` as strings). Builder A never reads AD-4 at all — it's not in their capability map (AD-4 binds CAP-4, owned by `decision_engine.py`) — so they have no reason to keep `line_id` values in a strictly-comparable format, and nothing stops a future seed extension from assigning `line_id`s out of chronological/insertion order for a given claim.

Both builders are individually correct against their own AD. But AD-4's "ascending" is only a well-defined, stable tie-break if `line_id` ordering has a guaranteed relationship to *original entry order or date* — and no AD says `line_id` has that property, or that it's the load script's job to preserve it. If Builder A's seed (or a later holdout-set seed for the last 10 claims, generated separately per BRIEF.md) ever produces non-lexicographically-monotonic `line_id`s within a same-date duplicate group, Builder B's "ascending line_id" tie-break silently diverges from "earlier line item" — which is what POLICY.md 5.1 actually means ("the later one" is rejected, i.e. temporal order, not ID string order).

- **Ambiguous AD:** AD-4's Rule substitutes a proxy ("ascending `line_id`") for POLICY.md 5.1's actual criterion (temporal/entry order — "reject the later one"), without an AD establishing that `line_id` ordering *is* entry/temporal order, and without assigning any builder ownership of that guarantee.
- **Tightening:** Either (a) add a Rule to AD-6 or a new AD binding `load_seed.py`: "`line_id`s are assigned in strictly increasing lexicographic order matching each CSV's row order, which is submission/entry order; this ordering is a load-time guarantee decision_engine.py may rely on," or (b) change AD-4's Rule to break ties on the `line_items.csv` column that actually encodes entry order (if one exists) instead of `line_id`, removing the proxy assumption entirely.

---

## Finding 4 — `record_decision` upsert conflict target vs. re-decision of a rejected duplicate

**Pair:** MCP-server developer vs. eval-script developer, disagreeing on what an "upsert" means for CAP-8 scoring.

- **Builder A (mcp_server.py owner)** implements AD-3's Rule literally: `INSERT ... ON CONFLICT(line_id) DO UPDATE`, `line_id` as primary key. Re-running the agent on the same claim overwrites each row in place — this is exactly the Rule's stated intent ("prevents duplicate or appended rows when the agent re-runs").
- **Builder B (eval/run_eval.py owner)**, per AD-2 ("`decisions` has exactly the columns BRIEF.md's `record_decision(line_id, decision, clause)` implies") and CAP-8 ("reads `decisions` + `eval/labelled.csv`"), writes the eval to score **whatever is currently in `decisions`** at eval time, joined against `labelled.csv` by `line_id`. This is the only reading AD-2's schema permits, since there's no run/timestamp/attempt column — AD-2 explicitly forbids adding undocumented columns ("prevents a builder adding an undocumented explanation column").

Individually correct. The incompatibility surfaces the moment the agent is run **twice with different behavior** in between — e.g., once before a decision_engine bug fix, once after (a very likely sequence during the story's own development, per "Stay inside the story you were given" / iterative build-test loops). Builder A's upsert silently discards the prior run's row with no record that a change happened. Builder B's eval script has no way to distinguish "freshly correct" from "correct only because it was never re-run" from "stale row from a since-fixed bug that happens to still be sitting there because that line_id wasn't touched in the second run" (e.g., the agent was only invoked on a subset of claims the second time). AD-3's upsert Rule and AD-2's fixed-column Rule jointly make `decisions` a **destructively-overwritten cache with no provenance**, and CAP-8's eval, run against it, cannot tell whether it's scoring the latest agent logic or a mix of two runs' outputs — which directly threatens the "100%-exact-match" success metric AD-1 exists to protect, since eval results become order-of-operations-dependent across the same story.

- **Ambiguous AD:** Neither AD-2 nor AD-3 states whether `eval/run_eval.py` must trigger a fresh, full agent run over all scored claims immediately before reading `decisions`, or may read whatever state happens to be sitting in `app.db`. AD-3's Rule is precise about the SQL (upsert on `line_id`) but silent about the *eval protocol* that depends on that table being freshly and completely populated.
- **Tightening:** Add a Rule (to AD-2, or a new eval-scoped AD): "`eval/run_eval.py` is responsible for ensuring `decisions` reflects a single, complete, current run before scoring — either by invoking `run_agent.py` over every claim in `labelled.csv` itself, or by failing/warning if any `line_id` in `labelled.csv` is missing from `decisions`. Partial or stale `decisions` tables must not be silently scored as if complete."

---

## Finding 5 — `get_claim`'s line items: does it include claims from *other* employees/claims for 5.1 duplicate context?

**Pair:** MCP-server developer vs. decision-engine developer (a second, independent fork of the AD-4 boundary).

- **Builder A (decision_engine.py owner)** reads POLICY.md 5.1 closely: "same date, merchant and amount as an **earlier item from the same employee**" — note this says *same employee*, not *same claim*. An employee could plausibly submit two separate claims (e.g., `CL-2001` and a later `CL-2050`) each containing a duplicate line item. Builder A assumes `get_claim`'s line items are scoped to one `claim_id`, but reads AD-4's Rule — "duplicate detection ... computed only from the line items `get_claim` returns for the current `claim_id`" — as simply describing *today's* single-claim MVP limitation, and writes `decide_line_item`'s docstring/tests assuming that if `get_claim` ever returned items across claims for the same employee, the function should still find duplicates — i.e., builds `decision_engine.py` to accept whatever list of line items it's given and never itself enforces single-claim scoping.
- **Builder B (mcp_server.py owner)** reads the same AD-4 Rule as an instruction to *them*: "single-claim scoped" means `get_claim(claim_id)` must **only** ever return line items for that one `claim_id` — full stop, structurally guaranteed at the tool level, regardless of what POLICY.md 5.1's "same employee" wording might imply about cross-claim duplicates being a real (if out-of-scope) case. Builder B treats AD-4 as closing the door on cross-claim duplicates entirely, permanently, at the data-access layer.

Both readings are defensible against AD-4's literal text ("computed only from the line items `get_claim` returns for the current `claim_id`" is true whether you read it as describing a property of `get_claim`'s output or a constraint decision_engine.py must self-impose). The practical incompatibility: if a labelled eval case (or the holdout set) ever contains a genuine cross-claim same-employee duplicate per POLICY.md 5.1's literal wording, Builder A's decision_engine would (correctly, per policy) flag it as a duplicate *if* fed the right data — but Builder B's `get_claim` structurally cannot supply cross-claim data, so the bug (an under-detected duplicate, i.e. wrongly approving/flagging instead of rejecting) is invisible in code review of either module alone: `decision_engine.py`'s logic is right, `mcp_server.py`'s tool contract is "compliant" with AD-4, and the two together produce a wrong decision with no owner to blame per-module.

- **Ambiguous AD:** AD-4's Rule conflates two different claims: "duplicate detection is computed only from claim-scoped data" (a statement about what `get_claim` supplies) and "duplicate detection is single-claim scoped" (a statement about the business rule's actual reach, which POLICY.md 5.1 does not itself restrict to one claim). The Rule's justification ("prevents ... a fifth tool that BRIEF.md's contract doesn't include") is about tool count, not about whether AD-4 is a faithful narrowing of POLICY.md 5.1 or a knowing MVP simplification that under-implements it.
- **Tightening:** Make AD-4 explicit that it is a **scope reduction of POLICY.md 5.1**, not a restatement of it: "5.1 as implemented in this MVP is claim-scoped, not employee-scoped as POLICY.md's text literally allows; cross-claim duplicates are a known, accepted gap, out of scope until `get_claim` (or a new tool) is extended to return an employee's other claims. `decision_engine.py` must not assume or attempt to detect duplicates beyond what its `claim_line_items` argument contains." This removes Builder A's incentive to build for a cross-claim future the tool layer will never deliver, and records the gap instead of hiding it behind two individually-compliant modules.

---

## Verdict

The spine is precise about **table shapes, tool counts, and file boundaries** (AD-2, AD-3, AD-5, AD-6 are hard to violate accidentally) but underspecifies **the data shapes and protocols that cross those boundaries** — exactly where two independently-correct builders diverge. All five findings above are boundary-crossing questions (MCP wire format, tie-break key semantics, eval-vs-agent-run protocol, cross-module scope of a business rule) that the current ADs assign to "whichever module happens to touch it first," which is not the same as assigning them to a single owner.
