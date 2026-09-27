"""Export the latest run to web/results.json for the static dashboard.

Read-only and offline: decisions come from `app.db`, each line item's reason
(the LLM explanation) and token usage come from the most recent MLflow trace
per claim that actually called a model, and the eval score comes from
`eval/run_eval.py`. No model calls, no API keys.

A reason is only exported when that trace's recorded decision and clause
still match `app.db` -- otherwise it would explain a different decision.
"""

import importlib.util
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import mlflow

CASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CASE_DIR.parent.parent
DB_PATH = CASE_DIR / "app.db"
OUT_PATH = REPO_ROOT / "web" / "results.json"
MLFLOW_EXPERIMENT = "expense-claim-reviewer"
GATE_THRESHOLD = Decimal("500")


def _load_run_eval():
    spec = importlib.util.spec_from_file_location("run_eval", CASE_DIR / "eval" / "run_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_items() -> list[dict]:
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT li.line_id, li.claim_id, li.date, li.category, li.merchant, li.amount,"
            " li.has_receipt, li.description, e.name AS employee, d.decision, d.clause"
            " FROM line_items li"
            " JOIN decisions d ON d.line_id = li.line_id"
            " JOIN claims c ON c.claim_id = li.claim_id"
            " JOIN employees e ON e.employee_id = c.employee_id"
            " ORDER BY li.claim_id, li.line_id"
        ).fetchall()
    return [dict(row) for row in rows]


def _latest_real_traces() -> dict[str, "mlflow.entities.Trace"]:
    """Most recent trace per claim that has token usage, i.e. made a real LLM call.

    Test runs use a fake LLM and write traces with no token usage, so they're skipped.
    """
    mlflow.set_tracking_uri(f"sqlite:///{REPO_ROOT / 'mlflow.db'}")
    experiment = mlflow.get_experiment_by_name(MLFLOW_EXPERIMENT)
    if experiment is None:
        return {}
    infos = mlflow.search_traces(
        locations=[experiment.experiment_id],
        filter_string="trace.name LIKE 'claim_%'",
        include_spans=False,
        return_type="list",
        order_by=["timestamp_ms DESC"],
        max_results=10000,
    )
    latest: dict[str, str] = {}
    for trace in infos:
        if not trace.info.token_usage:
            continue
        claim_id = json.loads(trace.info.request_metadata.get("mlflow.traceInputs", "{}")).get("claim_id")
        if claim_id and claim_id not in latest:
            latest[claim_id] = trace.info.trace_id
    return {claim_id: mlflow.get_trace(trace_id) for claim_id, trace_id in latest.items()}


def export() -> dict:
    items = _read_items()
    traces = _latest_real_traces()

    tokens = {"input": 0, "output": 0, "total": 0}
    traced_at = []
    reasons: dict[str, str] = {}
    for trace in traces.values():
        usage = trace.info.token_usage
        tokens["input"] += usage.get("input_tokens", 0)
        tokens["output"] += usage.get("output_tokens", 0)
        tokens["total"] += usage.get("total_tokens", 0)
        traced_at.append(trace.info.timestamp_ms)
        outputs = trace.data.spans[0].outputs or {}
        for line_id, text in (outputs.get("explanations") or {}).items():
            reasons[line_id] = (text, outputs.get("decisions", {}).get(line_id))

    counts = {"approve": 0, "flag": 0, "reject": 0}
    out_items = []
    for item in items:
        counts[item["decision"]] += 1
        amount = Decimal(item["amount"])
        reason, traced = reasons.get(item["line_id"], (None, None))
        if traced != {"decision": item["decision"], "clause": item["clause"]}:
            reason = None
        out_items.append(
            {
                **item,
                "amount": str(amount),
                "reason": reason,
                "pending_signoff": item["decision"] == "approve" and amount > GATE_THRESHOLD,
            }
        )

    checks = _load_run_eval().evaluate()
    passed = sum(check.passed for check in checks)
    total = sum(check.total for check in checks)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "line_items": len(out_items),
            "claims": len({item["claim_id"] for item in out_items}),
            "decisions": counts,
            "pending_signoff": sum(item["pending_signoff"] for item in out_items),
            "with_reason": sum(item["reason"] is not None for item in out_items),
            "eval": {
                "score": round(100 * passed / total, 1) if total else None,
                "checks": [
                    {"name": check.name, "passed": check.passed, "total": check.total}
                    for check in checks
                ],
            },
            "tokens": {
                **tokens,
                "traced_claims": len(traces),
                "from": _iso(min(traced_at)) if traced_at else None,
                "to": _iso(max(traced_at)) if traced_at else None,
            },
        },
        "items": out_items,
    }


def _iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    results = export()
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    summary = results["summary"]
    print(
        f"Wrote {OUT_PATH}: {summary['line_items']} line items, "
        f"{summary['with_reason']} with a reason, eval {summary['eval']['score']}%, "
        f"{summary['tokens']['total']} tokens."
    )
