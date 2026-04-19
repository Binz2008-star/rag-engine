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
"""

import json
import sys
from pathlib import Path

REPORT_PATH = Path("reports/ci_eval_strict.json")

if not REPORT_PATH.exists():
    print(f"FAIL: report not found at {REPORT_PATH}", file=sys.stderr)
    sys.exit(2)

with REPORT_PATH.open(encoding="utf-8") as f:
    report = json.load(f)

decision = report.get("decision")
failed_checks = report.get("failed_checks", [])
metrics = report.get("metrics", {})

if decision is None:
    print("FAIL: report missing 'decision' field — eval_runner.py must emit canonical gate output", file=sys.stderr)
    sys.exit(2)

print(f"Decision:            {decision}")
print(f"Pass rate:           {metrics.get('pass_rate', 0) * 100:.1f}%")
print(f"Hallucination rate:  {metrics.get('hallucination_rate', 0) * 100:.1f}%")
print(f"Refusal accuracy:    {metrics.get('refusal_accuracy', 0) * 100:.1f}%")
print(f"Domain accuracy:     {metrics.get('domain_accuracy', 0) * 100:.1f}%")
print(f"OCR presence check:  {metrics.get('ocr_presence_check', False)}")

if decision != "PROMOTE":
    print(f"\nFAIL: canonical gate rejected the run.")
    print(f"Failed checks: {failed_checks}")
    sys.exit(1)

print("\nPASS: canonical gate promoted the run.")
