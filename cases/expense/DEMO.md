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
5. **The traces.** `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db`, then open the `expense-claim-reviewer` experiment. There is one trace per claim, and its output holds the decisions and the explanations.

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

## Known before the demo (2026-09-27 run)

- Groq's daily token limit for `openai/gpt-oss-20b` (200,000 tokens) ran out during the second full run of the day, and Gemini's 20 free requests were already used. CL-2020 to CL-2040 therefore show explanations from the earlier clean run of the same day. The decisions are identical, so `export_results.py` and the judge accept them.
- The judge scored clarity 159/159 and clause citation 156/159. L-3016, L-3024 and L-3095 are flagged because their explanations cite the 20%-band rule (2.4) instead of, or as well as, the recorded clause. It is a wording issue; the decisions are correct.
