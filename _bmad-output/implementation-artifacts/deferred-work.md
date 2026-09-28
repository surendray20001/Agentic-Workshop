## Deferred from: code review of story-2-1-generate-and-trace-explanations (2026-09-27)

- source_spec: `_bmad-output/specs/spec-expense-epic-2/stories/2-1-generate-and-trace-explanations.md`
  summary: AGENTS.md documents a Gemini agent default and a Groq judge default, but no Groq agent default — Story 2-1's code (openai/gpt-oss-20b) fills that gap without an AGENTS.md update.
  evidence: Fix would edit an agent-context file, out of code review's scope; root AGENTS.md doesn't currently document every case's provider-fallback model choice.

## Deferred from: code review of 1-5-score-recorded-decisions-against-labelled-csv.md (2026-09-27)

- source_spec: `_bmad-output/specs/spec-epic-1/stories/1-5-score-recorded-decisions-against-labelled-csv.md`
  summary: `cases/expense/AGENTS.md` "Commands" lists only `run_eval.py`, not Epic 1's `uv run python cases/expense/eval/run_decision_eval.py`.
  evidence: Fix edits an agent-context file, out of a story's scope.

## Deferred from: code review of 2-3-judge-explanations-with-an-llm-judge.md (2026-09-27)

- source_spec: `_bmad-output/specs/spec-expense-epic-2/stories/2-3-judge-explanations-with-an-llm-judge.md`
  summary: `cases/expense/AGENTS.md` doesn't document `uv run python cases/expense/eval/judge_explanations.py`, its cost (~40 Groq calls, ~7 min) or its exit codes (0/1/2).
  evidence: Fix edits an agent-context file, out of a story's scope.
