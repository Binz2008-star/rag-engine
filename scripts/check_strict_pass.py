"""
Strict CI gate: enforces canonical promotion policy.

Reads the eval report produced by `eval_runner.py --mode strict` and
exits non-zero if the canonical gate rejects the run.

Canonical policy (from evaluation/eval_gate.py):
  - pass_rate >= 0.95
  - grounding_failure_rate == 0.0
  - refusal_accuracy == 1.0
  - domain_accuracy >= 0.95
  - ocr_presence_check == True
  - killer_failure: every killer query must have passed
"""

import json
import os
import sys
from pathlib import Path

# Path is env-overridable so this script works for both strict and dev
# workflows. Default stays backward-compatible with existing invocations.
REPORT_PATH = Path(os.environ.get("REPORT_PATH", "reports/ci_eval_strict.json"))
KILLER_CHECK = "killer_failure"


def _failing_killer_queries(results: list) -> list[dict]:
    """Return results rows flagged as killer that did not pass.

    Emits a stderr warning when NO rows carry ``killer: true``. This
    guards against silent regressions in ``eval_runner.py`` that would
    drop the killer metadata, causing ``_check_killers()`` in the gate
    to quietly return ``[]`` and a diagnostic block that claims
    ``0 failing`` on an otherwise rejected run.
    """
    if not isinstance(results, list):
        return []

    killer_rows = [
        row for row in results
        if isinstance(row, dict) and row.get("killer") is True
    ]

    if not killer_rows:
        print(
            "WARNING: no result rows carry 'killer: true' — "
            "verify eval_runner.py propagates query metadata to results.",
            file=sys.stderr,
        )

    return [row for row in killer_rows if row.get("passed") is not True]


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
    print(f"Grounding failure rate:  {metrics.get('grounding_failure_rate', 0) * 100:.1f}%")
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
