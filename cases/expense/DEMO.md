# Case Expenses: demo runbook

Run every command from the repo root. Keys come from `.env` (`GROQ_API_KEY`, `GEMINI_API_KEY`); none is ever printed.

## Before the demo (about 15 minutes)

| Step | Command | Expect |
|---|---|---|
| 1. Load the seed | `uv run python cases/expense/load_seed.py` | `Loaded seed data into …/cases/expense/app.db` |
| 2. Run the agent on all 40 claims | `PROVIDER=groq uv run python cases/expense/run_agent.py` | `Recorded 159 line-item decisions` after about 6 minutes, with no `warning:` lines |
| 3. Refresh the dashboard data | `uv run python cases/expense/export_results.py` | `159 line items, 159 with a reason, eval 100.0%` |

Use `PROVIDER=groq`, because Gemini's free tier allows 20 requests a day and a full run needs 40.

## Live (about 2 minutes plus the judge)

1. **The decisions are right.** `uv run python cases/expense/eval/run_eval.py` shows decision 119/119, clause 119/119, and reimbursable total 30/30 across the 30 labelled claims. Exit 0.
2. **Epic 1's own check.** `uv run python cases/expense/eval/run_decision_eval.py` shows decision and clause match only.
3. **The explanations are good.** `uv run python cases/expense/eval/judge_explanations.py` has Groq's `JUDGE_MODEL` rate every explanation for clarity and clause citation. It takes about 7 minutes and 40 calls, so run it before the demo and show the output.
4. **The dashboard.** `python -m http.server -d web 8000`, then open http://localhost:8000. It shows decision counts, the 25 approvals over $500 awaiting sign-off, the eval score, token usage, a decision filter, and every line's badge, reason and clause.
5. **The traces.** `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001`, then open http://localhost:5001 and the `expense-claim-reviewer` experiment. Use port 5001, because macOS's AirPlay Receiver holds port 5000. There is one trace per claim, and its output holds the decisions and the explanations.

## Points worth saying

- **Deterministic decisions.** `decision_engine.py` applies `POLICY.md` in plain code. The LLM only writes the explanation and never picks a decision or clause, so the 10 unlabelled holdout claims are decided by the same rules.
- **The $500 gate.** Any approval over $500 waits for a person's sign-off, per line item. It is derived from the recorded decision; no status is stored.
- **Untrusted text.** Claim descriptions are fenced as data in every prompt.
- **CI.** It runs on every push and PR, installs with uv, rebuilds `app.db`, runs the tests with no keys and no model calls, and builds `web/`.

## If something goes wrong

| Symptom | Fix |
|---|---|
| `warning: CL-…: no explanations (… 429 …)` | Groq's per-minute limit ran out after retries. Re-run step 2; decisions are always recorded. |
| `Cannot score: … partial run` | A debug run left `decisions` incomplete. Re-run step 2. |
| `Cannot judge: … differs from app.db` | The traces are older than `app.db`. Re-run step 2, then the judge. |
| The dashboard says `Couldn't load /results.json` | Serve `web/` as the site root (step 4); don't open the file directly. |

## Latest full run (2026-09-27, 19:50)

- All 40 claims were explained in one clean Groq run: no rate-limit warnings and no uncited clauses. Decisions scored 100% (119/119, 119/119, 30/30).
- The judge scored clarity 159/159 and clause citation 158/159. The one flag, L-3062, is a judgment call: the explanation cites the recorded clause 2.1 (matching the label), and the judge wanted 2.4's 20% band cited as well.
- Token usage across the 40 traced claims was 84,627.
- Groq free tier: `openai/gpt-oss-20b` allows 200,000 tokens a day, which is enough for about two full runs. Gemini allows 20 requests a day, which is not enough for one full run.
