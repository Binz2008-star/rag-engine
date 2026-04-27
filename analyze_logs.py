"""Failure mining script - analyzes query logs and classifies errors."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.config import BASE_DIR

LOGS_DIR = BASE_DIR / "logs"
QUERY_LOG_FILE = LOGS_DIR / "queries.jsonl"


def load_logs() -> List[Dict[str, Any]]:
    """Load all query logs from JSONL file."""
    if not QUERY_LOG_FILE.exists():
        print(f"No log file found at {QUERY_LOG_FILE}")
        return []

    logs = []
    with open(QUERY_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line))
    return logs


def analyze_logs(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze logs and extract patterns."""
    if not logs:
        return {}

    total = len(logs)

    # Basic metrics
    refusals = sum(1 for log in logs if log.get("is_refusal", False))
    refusal_rate = refusals / total if total else 0

    avg_retrieval_time = sum(log.get("retrieval_time_seconds", 0) for log in logs) / total
    avg_generation_time = sum(log.get("generation_time_seconds", 0) for log in logs) / total
    avg_total_time = sum(log.get("total_time_seconds", 0) for log in logs) / total

    # Source distribution
    source_counts: Counter = Counter()
    for log in logs:
        for source in log.get("sources", []):
            source_counts[source] += 1

    # Query length distribution
    query_lengths = [len(log.get("query", "")) for log in logs]
    avg_query_length = sum(query_lengths) / len(query_lengths) if query_lengths else 0
    max_query_length = max(query_lengths) if query_lengths else 0

    # Answer length distribution
    answer_lengths = [len(log.get("answer", "")) for log in logs]
    avg_answer_length = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0

    # Temporal distribution (hour of day)
    hour_distribution: Counter = Counter()
    for log in logs:
        timestamp = log.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour_distribution[dt.hour] += 1
            except:
                pass

    # Query patterns (first word analysis)
    first_words: Counter = Counter()
    for log in logs:
        query = log.get("query", "").strip()
        if query:
            first_word = query.split()[0].lower() if query.split() else ""
            if first_word:
                first_words[first_word] += 1

    # Intent buckets analysis
    intent_buckets: Counter = Counter()
    for log in logs:
        intent = log.get("intent", "unknown")
        intent_buckets[intent] += 1

    return {
        "total_queries": total,
        "refusals": refusals,
        "refusal_rate": refusal_rate,
        "avg_retrieval_time_seconds": avg_retrieval_time,
        "avg_generation_time_seconds": avg_generation_time,
        "avg_total_time_seconds": avg_total_time,
        "source_distribution": dict(source_counts.most_common(10)),
        "avg_query_length": avg_query_length,
        "max_query_length": max_query_length,
        "avg_answer_length": avg_answer_length,
        "hour_distribution": dict(hour_distribution.most_common()),
        "first_word_distribution": dict(first_words.most_common(10)),
        "intent_buckets": dict(intent_buckets.most_common()),
    }


def classify_failures(logs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Classify failures into categories aligned with evaluator taxonomy."""
    if not logs:
        return {}

    failures = defaultdict(list)

    for log in logs:
        query = log.get("query", "").strip()
        answer = log.get("answer", "").strip()
        sources = log.get("sources", [])
        is_refusal = log.get("is_refusal", False)
        failure_type = log.get("failure_type", None)

        # Classification aligned with evaluator taxonomy
        if failure_type:
            # Use the canonical failure_type from the system
            failure_key = str(failure_type)
            failures[failure_key].append(log)
        elif is_refusal:
            failures["refusal_failure"].append(log)
        elif not sources:
            failures["retrieval_miss"].append(log)
        elif len(answer) < 50:
            failures["short_answer"].append(log)
        elif len(answer) > 1000:
            failures["long_answer"].append(log)
        else:
            failures["successful"].append(log)

    return dict(failures)


def print_report(analysis: Dict[str, Any], failures: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print analysis report."""
    print("=" * 60)
    print("FAILURE MINING REPORT")
    print("=" * 60)

    if not analysis:
        print("No data to analyze.")
        return

    print(f"\nTotal queries: {analysis['total_queries']}")
    print(f"Refusals: {analysis['refusals']} ({analysis['refusal_rate']*100:.1f}%)")
    print(f"Avg retrieval time: {analysis['avg_retrieval_time_seconds']:.2f}s")
    print(f"Avg generation time: {analysis['avg_generation_time_seconds']:.2f}s")
    print(f"Avg total time: {analysis['avg_total_time_seconds']:.2f}s")

    print(f"\nSource distribution (top 10):")
    for source, count in analysis["source_distribution"].items():
        print(f"  {source}: {count}")

    print(f"\nQuery patterns:")
    print(f"  Avg query length: {analysis['avg_query_length']:.1f} chars")
    print(f"  Max query length: {analysis['max_query_length']} chars")
    print(f"  Avg answer length: {analysis['avg_answer_length']:.1f} chars")

    print(f"\nFirst word distribution (top 10):")
    for word, count in analysis["first_word_distribution"].items():
        print(f"  {word}: {count}")

    print(f"\nHour distribution:")
    for hour, count in analysis["hour_distribution"].items():
        print(f"  {hour:02d}:00: {count}")

    print(f"\nFailure classification:")
    for category, items in failures.items():
        print(f"  {category}: {len(items)}")

    print(f"\nSample failures:")
    for category, items in failures.items():
        if category != "successful" and items:
            print(f"\n[{category}]")
            for log in items[:3]:
                print(f"  - {log.get('query', 'N/A')}")

    print("=" * 60)


def main() -> None:
    """Main entry point."""
    logs = load_logs()

    if not logs:
        print("No logs to analyze. Run some queries first.")
        return

    analysis = analyze_logs(logs)
    failures = classify_failures(logs)

    print_report(analysis, failures)

    # Save detailed report
    report_file = LOGS_DIR / "analysis_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "analysis": analysis,
            "failures": {k: len(v) for k, v in failures.items()},
            "sample_failures": {
                k: v[:5] for k, v in failures.items()
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report saved to {report_file}")


if __name__ == "__main__":
    main()
