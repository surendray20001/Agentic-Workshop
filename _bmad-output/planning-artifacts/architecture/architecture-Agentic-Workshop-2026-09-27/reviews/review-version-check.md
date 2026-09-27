# Version/Reality Check — ARCHITECTURE-SPINE.md (Expense Claim Reviewer)

Reviewed: `_bmad-output/planning-artifacts/architecture/architecture-Agentic-Workshop-2026-09-27/ARCHITECTURE-SPINE.md`
Checked against: `pyproject.toml` (repo root) + live web search, 2026-09-27.

## 1. Does the Stack table match `pyproject.toml`?

Yes, exactly. Line-by-line diff:

| pyproject.toml | Spine's Stack table | Match |
| --- | --- | --- |
| `requires-python = ">=3.12"` | Python >=3.12 | ✅ |
| `langchain>=1.0` | langchain >=1.0 | ✅ |
| `langchain-google-genai>=2.1` | langchain-google-genai >=2.1 | ✅ |
| `langchain-groq>=0.3` | langchain-groq >=0.3 | ✅ |
| `langchain-mcp-adapters>=0.1` | langchain-mcp-adapters >=0.1 | ✅ |
| `mcp>=1.9` | mcp >=1.9 | ✅ |
| `mlflow>=3.4` | mlflow >=3.4 | ✅ |
| `pydantic>=2.8` | pydantic >=2.8 | ✅ |
| `python-dotenv>=1.0` | python-dotenv >=1.0 | ✅ |

The spine correctly labels this "reused as-is... brownfield, no new dependency introduced," and no version in the table was invented or adjusted from what's actually pinned in the repo. This part of the review passes cleanly.

## 2. Web reality-check of each pinned minimum

### `langchain>=1.0` and the `create_agent` reference (AD-1, Deferred section)
**Confirmed current, no issue.** `create_agent` (imported from `langchain.agents`) is LangChain's present-day, documented agent entry point, built on LangGraph's execution engine. LangChain is now at 1.4.x. The spine doesn't literally cite `create_agent` by name (the "Exact LangChain agent prompt and tool-calling loop wiring" is explicitly deferred to implementation), so there's nothing to falsify here — but it's worth flagging for the implementer: the old `AgentExecutor` / `create_react_agent` pattern that circulates in most pre-2026 tutorials was moved out of core `langchain` into a separate `langchain-classic` package at the 1.0 cut. Anyone building against outdated training data/tutorials could reach for the wrong API. Not a spine defect, but worth a one-line implementation note.

### `mcp>=1.9` — **STALE, needs attention**
This is the one finding that actually matters. The MCP Python SDK shipped a **2.0.0 stable release on 2026-07-28** with significant breaking changes (FastMCP renamed to MCPServer, `streamablehttp_client` renamed to `streamable_http_client` and changed from a 3-tuple to a 2-tuple return, camelCase→snake_case type fields, HTTP stack moved to `httpx2`). Because `mcp>=1.9` has **no upper bound**, `uv sync` today would pull whatever the current `mcp` release is — if that resolves to a 2.x line, this repo's `mcp_server.py` (built against 1.x-era APIs) would break or silently misbehave. The MCP maintainers' own guidance is to pin `mcp>=1.9,<2` (or `>=1.28,<2`) until a deliberate migration. **Recommend the architecture spine (or an implementation note) call out that the `mcp` dependency needs an upper-bound pin (`<2`) to keep this brownfield reuse safe**, since the existing `pyproject.toml` doesn't have one either — this is a latent risk in the existing repo, not something the spine introduced, but the spine repeats the unbounded constraint without flagging it.

### `langchain-mcp-adapters>=0.1` — **deprecated upstream, but low risk here**
As of `langchain` 1.4.0 (released 2026-09-03), MCP support was folded into core LangChain under a new `langchain.mcp` namespace (built on FastMCP, replacing `MultiServerMCPClient` with a single `MCPAdapter` class), and the standalone `langchain-mcp-adapters` package is no longer being actively developed (current release ~0.2.1–0.3.x, functionally superseded). Since `pyproject.toml` pins `langchain>=1.0` (not `>=1.4`) and separately pins `langchain-mcp-adapters>=0.1` with no upper bound, `uv sync` could land on a `langchain-mcp-adapters` release from after the hand-off point, or the repo could end up on old-adapter + new-langchain combinations that were never tested together. This isn't a spine authoring error (the spine correctly says "reused as-is," and the case explicitly avoids introducing new dependencies) — but it is a real currency risk in the underlying pin set worth surfacing to whoever owns `pyproject.toml`, since the package this case's `mcp_server.py`/`run_agent.py` will import is on a deprecation path.

### `mlflow>=3.4` — current, no issue
MLflow's 3.x line is active and has moved well past 3.4 (3.11–3.15 range observed in 2026), with no signs of a 3.4-specific deprecation or removed API relevant to what the spine uses (tracing to a local SQLite backend store). No action needed; `>=3.4` is a reasonable floor.

### `langchain-google-genai>=2.1`, `langchain-groq>=0.3`, `pydantic>=2.8`, `python-dotenv>=1.0`
No evidence any of these are stale, renamed, or deprecated. `langchain-google-genai` is moving toward a 4.0 release that switches to the consolidated `google-genai` SDK — worth knowing about but not a contradiction of anything the spine asserts, since the spine doesn't reference internal APIs of this package.

### Model names referenced in root `AGENTS.md` (not the spine itself, but load-bearing context)
`gemini-3.8-flash` (default `MODEL` per `AGENTS.md`) and `openai/gpt-oss-120b` (default `JUDGE_MODEL` via Groq) both resolve to real, currently-documented models as of today. Not part of the spine's own Stack table, but since the spine's Consistency Conventions section explicitly defers model config to root `AGENTS.md`, it's fair to note these were reality-checked too and are fine.

## 3. Greenfield/starter defaults
N/A — this is explicitly brownfield reuse of an already-installed stack (confirmed above), not a scaffolded starter. No starter defaults to verify.

## Verdict

The Stack table itself is an honest, unaltered transcription of `pyproject.toml` — no fabricated or training-data-guessed versions there. The one substantive risk the spine doesn't surface is that its source-of-truth (`pyproject.toml`) carries two unbounded minimum pins — `mcp>=1.9` and `langchain-mcp-adapters>=0.1` — that sit on the wrong side of real, dated upstream breaking changes (MCP SDK 2.0 stable on 2026-07-28; `langchain-mcp-adapters` superseded by `langchain[mcp]` as of LangChain 1.4.0 on 2026-09-03). Since this spine's core mechanism (agent ↔ MCP tools ↔ decision engine) depends directly on both packages, recommend flagging an upper-bound pin (`mcp<2`) as a build-time check before Epic work starts on this case, even though fixing `pyproject.toml` itself is out of scope for this spine (root `pyproject.toml` is shared, brownfield, Saturday's).

## Sources consulted
- https://blog.langchain.com/langchain-langgraph-1dot0/
- https://reference.langchain.com/python/langchain/agents/factory/create_agent
- https://docs.langchain.com/oss/python/migrate/langchain-v1
- https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters
- https://py.sdk.modelcontextprotocol.io/migration/
- https://github.com/modelcontextprotocol/python-sdk/releases
- https://dev.to/milkyway008/the-mcp-python-sdk-20-broke-the-wrapper-libraries-heres-how-to-spot-it-and-pin-back-346n
- https://pypi.org/project/langchain-mcp-adapters/
- https://libraries.io/pypi/langchain-mcp-adapters
- https://pypi.org/project/mlflow/
- https://mlflow.org/releases/
- https://pypi.org/project/langchain-google-genai/
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
