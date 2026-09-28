"""Epic 1's eval: score the recorded decisions against eval/labelled.csv (Story 1-5, CAP-8).

Reports decision match and clause match per line item only. The per-claim
reimbursable-total check is Epic 2's (`run_eval.py`). Reuses `run_eval.evaluate()`
rather than a second scorer, so both commands always agree. Read-only; refuses a
missing db or a partial run exactly like `run_eval.py`.

Exit codes: 0 both checks passed, 1 a check failed, 2 cannot score.
"""

import importlib.util
import sys
from pathlib import Path


def _load_run_eval():
    # Load the sibling scorer by path: `eval/` isn't a package, and a bare
    # `import run_eval` could resolve to the repo's root eval/run_eval.py.
    spec = importlib.util.spec_from_file_location(
        "expense_run_eval", Path(__file__).resolve().parent / "run_eval.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = _load_run_eval()

EPIC_1_CHECKS = ("decision match", "clause match")


def evaluate() -> list:
    checks = [check for check in run_eval.evaluate() if check.name.startswith(EPIC_1_CHECKS)]
    if len(checks) != len(EPIC_1_CHECKS):
        # Never report success on nothing scored (e.g. a check renamed in run_eval.py).
        raise run_eval.NotEvalReady(
            f"expected {len(EPIC_1_CHECKS)} checks from run_eval.py, got {[c.name for c in checks]}"
        )
    return checks


def main() -> int:
    try:
        checks = evaluate()
    except run_eval.NotEvalReady as exc:
        print(f"Cannot score: {exc}", file=sys.stderr)
        return 2

    for check in checks:
        print(f"{'PASS' if check.ok else 'FAIL'}  {check.name}: {check.passed}/{check.total}")
        for mismatch in check.mismatches:
            print(f"      {mismatch}")
    all_ok = all(check.ok for check in checks)
    print("All checks passed." if all_ok else "Some checks failed.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
