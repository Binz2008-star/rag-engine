"""
Strict CI gate: enforces canonical promotion policy.

Reads the eval report produced by `eval_runner.py --mode strict` and
exits non-zero if the canonical gate rejects the run.

Canonical policy (from evaluation/eval_gate.py):
  - pass_rate >= 0.95
  - hallucination_rate == 0.0
  - refusal_accuracy == 1.0
  - domain_accuracy >= 0.95
  - ocr_presence_check == True
  - killer_failure: every killer query must have passed
"""

import json
import sys
from pathlib import Path

REPORT_PATH = Path("reports/ci_eval_strict.json")
KILLER_CHECK = "killer_failure"


def _failing_killer_queries(results: list) -> list[dict]:
    """Return results rows flagged as killer that did not pass."""
    if not isinstance(results, list):
        return []
    out: list[dict] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        if row.get("killer") is True and row.get("passed") is not True:
            out.append(row)
    return out


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"FAIL: report not found at {REPORT_PATH}", file=sys.stderr)
        return 2

    with REPORT_PATH.open(encoding="utf-8") as f:
        report = json.load(f)

    decision = report.get("decision")
    failed_checks = report.get("failed_checks", []) or []
    metrics = report.get("metrics", {}) or {}
    results = report.get("results", []) or []

    if decision is None:
        print(
            "FAIL: report missing 'decision' field — eval_runner.py must emit canonical gate output",
            file=sys.stderr,
        )
        return 2

    print(f"Decision:            {decision}")
    print(f"Pass rate:           {metrics.get('pass_rate', 0) * 100:.1f}%")
    print(f"Hallucination rate:  {metrics.get('hallucination_rate', 0) * 100:.1f}%")
    print(f"Refusal accuracy:    {metrics.get('refusal_accuracy', 0) * 100:.1f}%")
    print(f"Domain accuracy:     {metrics.get('domain_accuracy', 0) * 100:.1f}%")
    print(f"OCR presence check:  {metrics.get('ocr_presence_check', False)}")

    if decision != "PROMOTE":
        print("\nFAIL: canonical gate rejected the run.")
        print(f"Failed checks: {failed_checks}")

        if KILLER_CHECK in failed_checks:
            failing_killers = _failing_killer_queries(results)
            print(
                f"\n*** KILLER QUERY FAILURE ({len(failing_killers)} failing) ***",
                file=sys.stderr,
            )
            for row in failing_killers:
                query = row.get("query") or row.get("question") or "<unknown>"
                reasons = row.get("failure_reasons") or row.get("reasons") or []
                print(f"  - {query}", file=sys.stderr)
                for reason in reasons:
                    print(f"      reason: {reason}", file=sys.stderr)
        return 1

    print("\nPASS: canonical gate promoted the run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
