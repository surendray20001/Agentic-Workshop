---
title: 'Judge explanations with an LLM judge'
type: 'feature'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/specs/spec-expense-epic-2/SPEC.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** CAP-9 has no command. Nothing checks, before the demo, whether each traced explanation is clear and cites its recorded clause. Only the external live-demo judge would find out.

**Approach:** Add `cases/expense/eval/judge_explanations.py`.
- **Input:** it takes the explanations from the most recent real-LLM trace per claim, reusing `export_results.py`'s selection. Fake-LLM test traces are excluded.
- **Judge call:** one `JUDGE_MODEL` call per claim (default `openai/gpt-oss-120b`, via `ChatGroq` using `method="json_mode"`), 40 calls in all. The prompt gives `POLICY.md`, each line's recorded decision and clause as fixed facts, and the explanation, with the claim text and explanation fenced as untrusted data. For each line it returns `clear`, `cites_clause` and a short `reason`. The judge never re-decides.
- **Report:** per criterion, passed/total, plus every failing line with the judge's reason.
- **Exit codes:** 0 when all 159 pass, 1 when any line fails, 2 when it cannot judge (no real traces, no `GROQ_API_KEY`, or a judge response that doesn't cover the claim's lines). Transient and per-minute rate-limit errors are retried.
- **Scope:** it writes nothing to SQLite or MLflow, and it doesn't touch decision/clause scoring (Story 2-2).
- **Tests:** they use a fake judge and make no model calls.

</frozen-after-approval>

## Implementation Notes

- `cases/expense/eval/judge_explanations.py` reuses `export_results._latest_real_traces()` and `run_agent._is_transient`; one `JUDGE_MODEL` call per claim, `json_mode`, `temperature=0`. Tests: `tests/test_judge_explanations.py` (15), fake judge only.
- Live run (real Groq `openai/gpt-oss-120b`, before review patches): 40 calls, ~7 min, no rate-limit failures. clear 159/159, cites_clause 157/159. L-3024 is a real bad explanation: it says the hotel cost exceeded the limit by more than 20%, but the decision is flag. L-3095 is a judgment call; the judge would attribute the ≤20% reasoning to 2.4 rather than 2.2.
- After patches: the completeness and staleness checks pass on real data (40 claims, 159/159 lines traced and matching `app.db`, 0 empty explanations). The full live judge was not re-run, to save quota.
- Full suite with keys blanked (as in CI): 67 passed, 2 skipped. No model calls.

## Review Triage Log

- `medium` — A partial set of traces could exit 0 without judging all 159 (blind-hunter): patched — `_check_against_db` exits 2 unless every line item is traced; test added.
- `medium` — Traces with failed or empty explanations were sent to the paid judge (blind-hunter): patched — empty explanations fail both criteria with no model call; test added.
- `medium` — Traced decision/clause not checked against `app.db`, so stale traces were graded against the wrong clause (blind-hunter): patched — mismatch exits 2; test added.
- `medium` — Groq's per-day limit ("try again in 7m12.5s") was retried as transient (blind-hunter): patched — "per day" fails fast as cannot-judge; test added.
- `low` — Duplicate line_ids from the judge were hidden by the dict (blind-hunter): patched — ids compared as sorted lists; test added.
- `low` — A literal `</lines>` in untrusted text could close the fence (blind-hunter): patched — fence tags stripped from data; test added.
- `low` — No `temperature=0`, so verdicts could flip between runs (blind-hunter): patched.
- `low` — FakeJudge regex skipped double-quoted reprs (blind-hunter): patched.
- `low` — Claim-level fields (purpose) not in the prompt (blind-hunter): not worth fixing — the per-line fields carry every fact an explanation cites.
- `low` — Unexpected errors (IndexError, sqlite, missing POLICY.md) exit 1 via traceback (blind-hunter): not worth fixing — inputs are fixed; failures are loud; same as the other eval commands.
- `low` — Report lists only failures, with no claim_id and one reason shared by both criteria (blind-hunter): not worth fixing — failures are grouped under their criterion; printing all 159 verdicts would bury them.
- `low` — ChatGroq's own retries stack with the script's (blind-hunter): not worth fixing — bounded, and only on real errors.
- `false` — Story missing ACs/verification (blind-hunter): refuted — the one-shot route deletes those sections by design; live results recorded above.
- `defer` — The judge command, its cost (~40 Groq calls) and its exit codes aren't in `cases/expense/AGENTS.md` (blind-hunter): deferred — edits an agent-context file.

