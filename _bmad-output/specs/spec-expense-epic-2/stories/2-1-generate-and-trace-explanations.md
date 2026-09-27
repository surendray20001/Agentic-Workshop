---
title: 'Generate and trace explanations'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-expense-epic-2/SPEC.md']
baseline_commit: '3abe5b2095d493173795a35b215564722dee4f2d'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 1's `decisions` are correct but unexplained — BRIEF.md's judge check and the reviewer at the demo need a clear, clause-citing sentence per line item, and nothing currently produces or traces one.

**Approach:** Extend `cases/expense/run_agent.py` (Epic 1, done) with one LLM call per claim (not per line item — 40 calls, not 159) requesting structured output: an explanation per line item, citing the clause and the specific fact. Wrap the whole run in MLflow tracing so the judge (external to this codebase) can read explanations from the trace.

## Boundaries & Constraints

**Always:** One `ChatGoogleGenerativeAI` (or `ChatGroq` if `PROVIDER=groq`) call per claim, using `.with_structured_output()` with a Pydantic schema (`{explanations: [{line_id, explanation}]}`), given that claim's line items plus each one's already-decided `(decision, clause)` from `decision_engine.decide_claim`, and the full text of `POLICY.md` as context so the LLM can ground its wording in the actual clause. `record_decision`'s call and arguments are unchanged from Epic 1 — the explanation is never passed to it (Spine AD-2). `mlflow.set_tracking_uri("sqlite:///mlflow.db")`, `mlflow.set_experiment("expense-claim-reviewer")`, `mlflow.langchain.autolog()` at the top of `run_agent.py`, matching root `run_agent.py`'s pattern. Model selection reads `MODEL`/`PROVIDER`/`GEMINI_API_KEY`/`GROQ_API_KEY` from `.env` per root `AGENTS.md` — already confirmed live and working.

**Never:** Do not call the LLM to decide the decision or clause — those are fixed inputs from Story 1-2's engine (Spine AD-1). Do not persist explanation text to SQLite. Do not build the LLM judge itself (external, BRIEF.md's demo mechanism). Do not change `decision_engine.py`'s or `mcp_server.py`'s existing signatures.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full run produces explanations | All 40 claims, real LLM call | Every one of the 159 line items has a non-empty explanation string naming its clause | N/A |
| Structured output shape | One claim's LLM call | Response parses into `ClaimExplanations` with one `LineExplanation` per line item on that claim — no missing or extra line IDs | N/A |
| MLflow trace captures the call | Run wrapped in `mlflow.langchain.autolog()` | The LLM call (prompt + response) appears in a trace under experiment `expense-claim-reviewer` in `sqlite:///mlflow.db` | N/A |
| `.content` shape from Gemini | Direct (non-structured) call, for reference | Content is a list of blocks (`[{"type": "text", "text": ...}]`), not a plain string — only relevant if bypassing `.with_structured_output()`, which this story doesn't | N/A |

</frozen-after-approval>

## Code Map

- `cases/expense/run_agent.py` (Epic 1, done) — extend `run()`: after `decision_engine.decide_claim(...)` returns `decisions` for a claim, call the LLM once for that claim's explanations, then proceed to the existing `record_decision` loop unchanged.
- `run_agent.py` (root, Saturday's stub) — reference pattern for MLflow setup: `mlflow.set_tracking_uri("sqlite:///mlflow.db")`, `mlflow.set_experiment(...)`, `mlflow.langchain.autolog()`.
- `cases/expense/POLICY.md` — pass its full text as LLM context; it's short enough (46 lines) to include directly, no need to excerpt per clause.
- Confirmed via a live call: `ChatGoogleGenerativeAI(model="gemini-3.8-flash").with_structured_output(ClaimExplanations)` returns a correctly-typed, correctly-worded response today with the `.env` keys already present.
- `_bmad-output/specs/spec-expense-epic-2/SPEC.md` — CAP-7 (this story) and its constraints.

## Tasks & Acceptance

**Execution:**
- [ ] `cases/expense/run_agent.py` -- add `ClaimExplanations`/`LineExplanation` Pydantic models, an `_explain_claim(line_items, decisions, llm)` function, MLflow setup at module load, and wire the explanation call into `run()` between deciding and recording.
- [ ] `tests/test_run_agent.py` -- extend with a mocked-LLM unit test (explanation step doesn't alter recorded decisions) and one real-API smoke test (skipped if `GEMINI_API_KEY` is absent) proving structured output parses correctly for one real claim.

**Acceptance Criteria:**
- Given a full run with the explanation step wired in, when it completes, then `decisions` still has exactly 159 rows matching Epic 1's content exactly (explanations don't change what's recorded).
- Given one real claim, when the LLM call runs, then the response is a `ClaimExplanations` with one `LineExplanation` per line item on that claim, each `explanation` non-empty and mentioning its clause.
- Given the run completes, when the MLflow trace is inspected, then it shows LLM calls under the `expense-claim-reviewer` experiment in `sqlite:///mlflow.db`.

### Review Findings

- [x] [Review][Patch] `run_agent.run()`'s default LLM dependency broke Story 1-4's existing offline tests [cases/expense/run_agent.py:119; tests/test_run_agent.py] — fixed: added `tests/conftest.py`'s `fake_llm` fixture, injected into all 6 `run_agent.run()` call sites in `tests/test_run_agent.py`.
- [x] [Review][Patch] A single claim's explanation failure aborts the entire 40-claim run, losing decisions for every unprocessed claim [cases/expense/run_agent.py:145-169] — fixed: `_explain_claim` failures are caught per-claim in `run()`; decisions are always recorded regardless, failure noted in the span's `explanation_error` output.
- [x] [Review][Patch] MLflow setup (tracking_uri/experiment/autolog) re-runs on every `run()` call instead of once [cases/expense/run_agent.py:121-123] — fixed: `_configure_mlflow()` guards with a module-level flag.
- [x] [Review][Patch] `_explain_claim`'s returned dict isn't validated against the input line_ids [cases/expense/run_agent.py:88-98] — fixed: raises `ValueError` on any key mismatch, treated as non-transient (fails fast, no wasted retries).
- [x] [Review][Patch] No test exercises the retry/backoff path [tests/test_explanations.py] — fixed: added retry-then-succeed, fail-fast-on-non-transient-error, and explanation-failure-doesn't-block-decisions tests.
- [x] [Review][Patch] Groq's `openai/gpt-oss-20b` model choice has no automated regression test [cases/expense/run_agent.py:73] — fixed: added a skippable, real-API regression test; ran and passed against the real Groq API.
- [x] [Review][Defer] `AGENTS.md` documents a Gemini agent default and a Groq judge default, but no Groq agent default — this case's code fills the gap without an `AGENTS.md` update [cases/expense/run_agent.py:73] — deferred: fix would edit an agent-context file, out of code review's scope; root AGENTS.md doesn't currently need every case's provider fallback documented

#### Rejected

- `false` — Manual per-claim MLflow span duplicates autolog's output with no rationale (blind-hunter): refuted — this is exactly the "outer application boundary" pattern the `instrumenting-with-mlflow-tracing` skill recommends alongside autolog, and matches root `run_agent.py`'s own established convention.
- `false` — `last_error: Exception | None` then `raise last_error` could raise `None` (verification-gap): refuted — `_MAX_LLM_ATTEMPTS` is a fixed constant ≥1, so the loop always assigns `last_error` at least once before that line executes.
- `low` — POLICY.md missing at import crashes `run_agent` (edge-case-hunter): not worth fixing — `POLICY.md` is a read-only, fixed, always-present file, already verified multiple times this session.
- `low` — Missing API key produces a cryptic client error (edge-case-hunter): not worth fixing — unlikely in this documented, already-keyed demo environment.
- `low` — `line_items` could contain a line_id absent from `decisions` (edge-case-hunter): not worth fixing — unreachable by construction; `decisions` is built by `decision_engine.decide_claim` from that same `line_items` list.
- `low` — Tests write real traces into the shared root `mlflow.db` (edge-case-hunter, blind-hunter): not worth fixing — this is the intentional, documented shared-store design (Architecture Spine AD-7), not a defect.
- `low` — New tests live in `tests/test_explanations.py` instead of extending `tests/test_run_agent.py` as the spec's task list suggested (blind-hunter): not worth fixing — a coherent split by concern (orchestration vs. explanation), an implementation-level choice.
- `low` — No automated test asserts MLflow trace/span content directly (blind-hunter): not worth fixing — manually verified via live testing (4 spans, correct hierarchy observed); adding it couples tests to MLflow's internal API for marginal gain over the two other, already-tested acceptance criteria.
- `low` — A claim with zero line items would waste an LLM call (blind-hunter): not worth fixing — unreachable; no such claim exists anywhere in the fixed seed data (verified in Story 1-2).
- `low` — `POLICY_TEXT` read at module import time couples every import to `POLICY.md` (blind-hunter): not worth fixing — no current test needs to vary it; premature abstraction.
- `low` — Magic numbers (159, 40) hardcoded in test assertions (blind-hunter): not worth fixing — consistent with established, previously-unflagged precedent from Story 1-1's own tests.

### Review Findings (re-review, 2026-09-27)

- [x] [Review][Patch] (decided: ignore `MODEL` on Groq) `MODEL` is shared by both providers — `_get_llm()`'s Groq branch reads `MODEL` (AGENTS.md documents it as the Gemini agent model, default `gemini-3.8-flash`); with `MODEL=gemini-…` in `.env` and `PROVIDER=groq`, ChatGroq gets a Gemini model id and every explanation fails. `.env` sets no `MODEL` today. Fix needs a choice: ignore `MODEL` on Groq (hardcode `openai/gpt-oss-20b`), or introduce a Groq-specific var.
- [x] [Review][Patch] (decided: keep and flag in span + operator warning) Clause citation / non-empty text is never checked at runtime — `_explain_claim` validates only the line_id set; an empty or clause-less explanation reaches the trace unflagged (matrix row "every … explanation string naming its clause"). Fix needs a choice: treat as failure (retry/drop the claim's explanations) vs keep-and-flag in the span.
- [x] [Review][Patch] Live-API tests turn every exception into a skip, so the Groq "regression guard" can never fail on the regression it names [tests/test_explanations.py:149,287]
- [x] [Review][Patch] Explanation failures are silent to the operator; empty `str(exc)` drops the error entirely [cases/expense/run_agent.py:191-207]
- [x] [Review][Patch] Claim `description` (untrusted) is inlined into the prompt with no data delimiting or "ignore instructions in data" guard (AGENTS.md rule) [cases/expense/run_agent.py:109-124]
- [x] [Review][Patch] "Doesn't alter recorded decisions" test compares counts, not `(decision, clause)` rows (AC1 "matching Epic 1's content exactly") [tests/test_explanations.py:55-85]
- [x] [Review][Patch] Groq default model (`openai/gpt-oss-20b`) and `method="json_mode"` choice have no offline test [tests/test_explanations.py:301-307]
- [x] [Review][Patch] `test_get_llm_*` depend on the local `.env` — `_get_llm()`'s `load_dotenv()` re-adds a deleted `PROVIDER`/`MODEL` [tests/test_explanations.py:292-307]
- [x] [Review][Patch] Smoke-test skipif accepts either key, but `_get_llm()` needs the key for the configured provider [tests/test_explanations.py:122-125]
- [x] [Review][Patch] Explanation-failure test checks the returned counter, not persisted rows [tests/test_explanations.py:241-257]
- [x] [Review][Patch] (promoted from defer) `_is_transient` did not retry per-minute rate limits [cases/expense/run_agent.py:43-50,72-76] — settled by the live full `PROVIDER=groq` run: CL-2037 lost its explanations to Groq's TPM 429 ("try again in 862.5ms"). Fixed: "rate limit" is transient; any message mentioning "quota" stays non-transient.

#### Rejected (re-review)

- `low` — `with_structured_output` returning `None` raises `AttributeError` without retry (edge-case-hunter): not worth fixing — failure is caught per claim and recorded in `explanation_error`, same as any other explanation failure; adding a guard buys nothing.
- `low` — Duplicate line_ids in the LLM response collapse silently (edge-case-hunter): not worth fixing — requires a guard, and the duplicate still covers every line with a valid explanation.
- `false` — `_get_llm()` failure aborts the run and loses decisions (edge-case-hunter): refuted — it raises before `truncate_decisions()`, so existing decisions are untouched and the failure is loud.
- `low` — Relative `sqlite:///mlflow.db` depends on cwd (blind-hunter, edge-case-hunter): not worth fixing — the literal URI is mandated by this story's Always list and AGENTS.md, and matches root `run_agent.py`.
- `low` — Tests write traces into the real `mlflow.db` (edge-case-hunter): re-raise of an already-rejected finding (shared-store design, AD-7).
- `low` — Zero-line-item claim wastes an LLM call (edge-case-hunter): re-raise of an already-rejected finding; unreachable in fixed seed data.
- `low` — `_run_without_explanation_step` duplicates Story 1-4's `run()`; fixtures duplicated across test files (blind-hunter): not worth fixing — the copy is intentionally a frozen pre-2-1 baseline; consolidating fixtures is a refactor, not a direct fix.
- `low` — Story file task checkboxes unticked and Verification command omits `tests/test_explanations.py` (acceptance-auditor): rejected — fix would edit the spec under review.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest tests/test_run_agent.py -v` -- expected: all tests pass (mocked unit test always; real-API smoke test passes when `GEMINI_API_KEY` is set).
- `uv run python cases/expense/run_agent.py` -- expected: completes, `decisions` still has 159 rows, a new MLflow run appears under experiment `expense-claim-reviewer`.
