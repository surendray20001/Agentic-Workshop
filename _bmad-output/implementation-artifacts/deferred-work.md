- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-load-seed.md`
  summary: Enforce referential integrity between tickets and customers at load time (FK constraint, cross-CSV validation, insert-order dependency, and a covering test) instead of relying on query-time lookups in mcp/triage_server.py.
  evidence: Real gap for future robustness but not required by epic-1's CAP-1 success criteria (exact table/column match + idempotency); adding it now means PRAGMA foreign_keys handling, reordered inserts, and new tests beyond this story's scope.
