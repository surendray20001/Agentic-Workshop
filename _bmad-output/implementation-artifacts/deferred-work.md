## Deferred from: code review of story-2-1-generate-and-trace-explanations (2026-09-27)

- source_spec: `_bmad-output/specs/spec-expense-epic-2/stories/2-1-generate-and-trace-explanations.md`
  summary: AGENTS.md documents a Gemini agent default and a Groq judge default, but no Groq agent default — Story 2-1's code (openai/gpt-oss-20b) fills that gap without an AGENTS.md update.
  evidence: Fix would edit an agent-context file, out of code review's scope; root AGENTS.md doesn't currently document every case's provider-fallback model choice.
