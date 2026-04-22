#!/usr/bin/env python3
"""
Aggregate evaluation reports into a decision dashboard.

Reads all JSON reports from a directory (default: reports/), extracts
canonical metrics, and produces a trend summary. This enables tracking
performance over time: pass rates, hallucination rates, latency, and
domain accuracy across CI runs.

Output schema:
{
  "runs": [
    {"timestamp": 1234567890, "file": "reports/eval_123.json", "metrics": {...}}
  ],
  "trends": {
    "pass_rate": [{"timestamp": 1234567890, "value": 0.95}, ...],
    "hallucination_rate": [...],
    "latency_s": [...],
    "domain_accuracy": [...],
    "refusal_accuracy": [...]
  },
  "summary": {
    "total_runs": N,
    "avg_pass_rate": 0.X,
    "latest_pass_rate": 0.X,
    "pass_rate_direction": "up/down/stable",
    "latest_hallucination_rate": 0.X,
    "latest_latency_s": 0.X
  }
}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def extract_timestamp_from_filename(filename: str) -> int | None:
    """Extract Unix timestamp from filename patterns like eval_1234567890.json."""
    # Pattern: eval_<timestamp>.json
    match = re.search(r"eval_(\d+)\.json", filename)
    if match:
        return int(match.group(1))
    # Pattern: ci_eval_strict_*.json (no timestamp, use file mtime)
    return None


def load_reports(report_dir: Path) -> list[dict[str, Any]]:
    """Load all JSON reports from directory, sorted by timestamp."""
    if not report_dir.exists():
        print(f"ERROR: Report directory not found: {report_dir}", file=sys.stderr)
        sys.exit(2)

    reports = []
    for file_path in sorted(report_dir.glob("*.json")):
        # Skip non-eval files (e.g., suggestions.json)
        if file_path.name in ("suggestions.json", "ingestion_audit.json"):
            continue

        try:
            with file_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"WARNING: Skipping invalid JSON {file_path.name}: {e}", file=sys.stderr)
            continue

        # Extract timestamp from filename or file mtime
        timestamp = extract_timestamp_from_filename(file_path.name)
        if timestamp is None:
            timestamp = int(file_path.stat().st_mtime)

        reports.append({
            "timestamp": timestamp,
            "file": str(file_path.relative_to(file_path.parent.parent)),
            "metrics": data.get("metrics", {}),
            "decision": data.get("decision"),
            "failed_checks": data.get("failed_checks", []),
        })

    # Sort by timestamp ascending
    reports.sort(key=lambda r: r["timestamp"])
    return reports


def compute_trends(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute trend data for canonical metrics."""
    trends: dict[str, list[dict[str, Any]]] = {
        "pass_rate": [],
        "hallucination_rate": [],
        "latency_s": [],
        "domain_accuracy": [],
        "refusal_accuracy": [],
    }

    for report in reports:
        metrics = report["metrics"]
        ts = report["timestamp"]

        trends["pass_rate"].append({"timestamp": ts, "value": metrics.get("pass_rate")})
        trends["hallucination_rate"].append({"timestamp": ts, "value": metrics.get("hallucination_rate")})
        trends["latency_s"].append({"timestamp": ts, "value": metrics.get("avg_elapsed_s")})
        trends["domain_accuracy"].append({"timestamp": ts, "value": metrics.get("domain_accuracy")})
        trends["refusal_accuracy"].append({"timestamp": ts, "value": metrics.get("refusal_accuracy")})

    return trends


def compute_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary statistics across all runs."""
    if not reports:
        return {"total_runs": 0}

    latest = reports[-1]["metrics"]
    pass_rates = [r["metrics"].get("pass_rate") for r in reports if r["metrics"].get("pass_rate") is not None]

    if not pass_rates:
        return {
            "total_runs": len(reports),
            "latest_pass_rate": latest.get("pass_rate"),
            "latest_hallucination_rate": latest.get("hallucination_rate"),
            "latest_latency_s": latest.get("avg_elapsed_s"),
        }

    avg_pass_rate = sum(pass_rates) / len(pass_rates)
    latest_pass_rate = latest.get("pass_rate")
    prev_pass_rate = reports[-2]["metrics"].get("pass_rate") if len(reports) > 1 else None

    # Determine direction
    if prev_pass_rate is None:
        direction = "stable"
    elif latest_pass_rate > prev_pass_rate:
        direction = "up"
    elif latest_pass_rate < prev_pass_rate:
        direction = "down"
    else:
        direction = "stable"

    return {
        "total_runs": len(reports),
        "avg_pass_rate": round(avg_pass_rate, 3),
        "latest_pass_rate": round(latest_pass_rate, 3) if latest_pass_rate is not None else None,
        "pass_rate_direction": direction,
        "latest_hallucination_rate": latest.get("hallucination_rate"),
        "latest_latency_s": latest.get("avg_elapsed_s"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate evaluation reports into a decision dashboard"
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports"),
        help="Directory containing JSON evaluation reports (default: reports/)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/aggregated_trends.json"),
        help="Output path for aggregated trends JSON"
    )
    args = parser.parse_args()

    reports = load_reports(args.report_dir)
    if not reports:
        print(f"WARNING: No valid reports found in {args.report_dir}", file=sys.stderr)
        return 0

    trends = compute_trends(reports)
    summary = compute_summary(reports)

    output = {
        "runs": reports,
        "trends": trends,
        "summary": summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Aggregated {len(reports)} reports → {args.output}")
    print(f"  Total runs: {summary['total_runs']}")
    print(f"  Avg pass rate: {summary.get('avg_pass_rate', 'N/A')}")
    print(f"  Latest pass rate: {summary.get('latest_pass_rate', 'N/A')}")
    print(f"  Direction: {summary.get('pass_rate_direction', 'N/A')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
