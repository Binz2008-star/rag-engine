"""Regression tracking script - compares two eval reports and highlights changes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


def load_report(report_path: Path) -> Dict[str, Any]:
    """Load an eval report from JSON file."""
    if not report_path.exists():
        print(f"ERROR: Report not found: {report_path}")
        sys.exit(2)

    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_metrics(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """Compare metrics between two reports."""
    print("=" * 60)
    print("METRICS COMPARISON")
    print("=" * 60)

    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})

    metrics_to_compare = [
        ("pass_rate", "Pass rate"),
        ("source_match_accuracy", "Source match accuracy"),
        ("top1_source_accuracy", "Top-1 source accuracy"),
        ("source_precision", "Source precision"),
        ("refusal_accuracy", "Refusal accuracy"),
        ("avg_elapsed_s", "Avg latency"),
    ]

    for key, label in metrics_to_compare:
        before_val = before_metrics.get(key)
        after_val = after_metrics.get(key)

        if before_val is None or after_val is None:
            print(f"\n{label}: N/A (missing data)")
            continue

        if "rate" in key or "accuracy" in key:
            before_pct = before_val * 100
            after_pct = after_val * 100
            delta = after_pct - before_pct
            delta_str = f"+{delta:.1f}%" if delta >= 0 else f"{delta:.1f}%"
            print(f"\n{label}:")
            print(f"  Before: {before_pct:.1f}%")
            print(f"  After:  {after_pct:.1f}%")
            print(f"  Delta:  {delta_str}")
        else:
            delta = after_val - before_val
            delta_str = f"+{delta:.2f}s" if delta >= 0 else f"{delta:.2f}s"
            print(f"\n{label}:")
            print(f"  Before: {before_val:.2f}s")
            print(f"  After:  {after_val:.2f}s")
            print(f"  Delta:  {delta_str}")


def compare_failure_buckets(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """Compare failure buckets between two reports."""
    print("\n" + "=" * 60)
    print("FAILURE BUCKET COMPARISON")
    print("=" * 60)

    before_buckets = before.get("metrics", {}).get("failure_buckets", {})
    after_buckets = after.get("metrics", {}).get("failure_buckets", {})

    all_buckets = set(before_buckets.keys()) | set(after_buckets.keys())

    if not all_buckets:
        print("\nNo failure buckets to compare.")
        return

    print(f"\n{'Bucket':<30} {'Before':>10} {'After':>10} {'Delta':>10}")
    print("-" * 62)

    for bucket in sorted(all_buckets):
        before_count = before_buckets.get(bucket, 0)
        after_count = after_buckets.get(bucket, 0)
        delta = after_count - before_count
        delta_str = f"+{delta}" if delta > 0 else str(delta)

        print(f"{bucket:<30} {before_count:>10} {after_count:>10} {delta_str:>10}")

    # Top bucket changes
    top_changes = sorted(
        ((b, after_buckets.get(b, 0) - before_buckets.get(b, 0)) for b in all_buckets),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    print("\nTop bucket changes:")
    for b, d in top_changes[:3]:
        print(f"  {b}: {d:+}")


def compare_test_results(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """Compare individual test results between two reports."""
    print("\n" + "=" * 60)
    print("TEST RESULT CHANGES")
    print("=" * 60)

    before_results = {r["test_id"]: r for r in before.get("results", [])}
    after_results = {r["test_id"]: r for r in after.get("results", [])}

    all_test_ids = set(before_results.keys()) | set(after_results.keys())

    regressions = []
    improvements = []
    unchanged = []

    for test_id in sorted(all_test_ids):
        before_result = before_results.get(test_id)
        after_result = after_results.get(test_id)

        if before_result is None:
            improvements.append(f"  [NEW] Test {test_id}: {after_result.get('question', 'N/A')[:50]}... → {'PASS' if after_result.get('passed') else 'FAIL'}")
            continue

        if after_result is None:
            regressions.append(f"  [REMOVED] Test {test_id}: {before_result.get('question', 'N/A')[:50]}... → {'PASS' if before_result.get('passed') else 'FAIL'}")
            continue

        before_passed = before_result.get("passed", False)
        after_passed = after_result.get("passed", False)

        if before_passed and not after_passed:
            question = after_result.get("question", "N/A")
            reasons = after_result.get("reasons", [])
            regressions.append(f"  [REGRESSION] Test {test_id}: {question[:50]}...")
            if reasons:
                regressions.append(f"    Reasons: {', '.join(reasons)}")
        elif not before_passed and after_passed:
            question = after_result.get("question", "N/A")
            improvements.append(f"  [IMPROVEMENT] Test {test_id}: {question[:50]}...")
        else:
            unchanged.append(f"  [UNCHANGED] Test {test_id}: {'PASS' if after_passed else 'FAIL'}")

    regression_tests = [r for r in regressions if "[REGRESSION]" in r]
    improvement_tests = [r for r in improvements if "[IMPROVEMENT]" in r]

    if regression_tests:
        print(f"\nRegressions ({len(regression_tests)}):")
        for line in regressions:
            print(line)

    if improvement_tests:
        print(f"\nImprovements ({len(improvement_tests)}):")
        for line in improvements:
            print(line)


def print_summary(before: Dict[str, Any], after: Dict[str, Any]) -> None:
    """Print overall summary."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})

    before_pass = before_metrics.get("passed", 0)
    after_pass = after_metrics.get("passed", 0)
    before_total = before_metrics.get("total", 0)
    after_total = after_metrics.get("total", 0)

    delta_pass = after_pass - before_pass
    delta_str = f"+{delta_pass}" if delta_pass >= 0 else str(delta_pass)

    print(f"\nTotal tests: {before_total} → {after_total}")
    print(f"Passed tests: {before_pass} → {after_pass} ({delta_str})")
    print(f"Pass rate: {before_metrics.get('pass_rate', 0)*100:.1f}% → {after_metrics.get('pass_rate', 0)*100:.1f}%")

    # Latency regression detection
    before_lat = before_metrics.get("avg_elapsed_s", 0)
    after_lat = after_metrics.get("avg_elapsed_s", 0)
    if before_lat > 0 and after_lat > before_lat * 1.2:
        print(f"\n⚠️ Latency regression: {before_lat:.2f}s → {after_lat:.2f}s (>20%)")

    if delta_pass > 0:
        print("\n✓ IMPROVEMENT: More tests passing")
    elif delta_pass < 0:
        print("\n✗ REGRESSION: Fewer tests passing")
    else:
        print("\n= NO CHANGE: Same number of tests passing")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare two eval reports for regression tracking")
    parser.add_argument("before", type=Path, help="Path to 'before' report (baseline)")
    parser.add_argument("after", type=Path, help="Path to 'after' report (new run)")
    args = parser.parse_args()

    before_report = load_report(args.before)
    after_report = load_report(args.after)

    print(f"\nComparing:")
    print(f"  Before: {args.before}")
    print(f"  After:  {args.after}")

    compare_metrics(before_report, after_report)
    compare_failure_buckets(before_report, after_report)
    compare_test_results(before_report, after_report)
    print_summary(before_report, after_report)

    print("\n" + "=" * 60)

    before_pass_rate = before_report.get("metrics", {}).get("pass_rate", 0)
    after_pass_rate = after_report.get("metrics", {}).get("pass_rate", 0)

    before_source_acc = before_report.get("metrics", {}).get("source_match_accuracy", 0)
    after_source_acc = after_report.get("metrics", {}).get("source_match_accuracy", 0)

    # Regression detection: check both pass rate and source accuracy
    if after_pass_rate < before_pass_rate:
        return 1  # Pass rate regression detected
    elif after_source_acc < before_source_acc:
        return 1  # Source accuracy regression detected
    elif after_pass_rate > before_pass_rate:
        return 0  # Improvement
    else:
        return 0  # No change


if __name__ == "__main__":
    sys.exit(main())
