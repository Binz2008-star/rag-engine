#!/usr/bin/env python3
"""Compare two snapshot directories and report differences.

Usage:
    python scripts/diff_snapshots.py --before reports/before --after reports/after
    python scripts/diff_snapshots.py --before reports/before --after reports/after_ingest
    python scripts/diff_snapshots.py --before reports/after_fix --after reports/after_fix_v2
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def format_delta(before: float, after: float, as_percent: bool = False) -> str:
    """Format a delta between two values."""
    delta = after - before
    sign = "+" if delta > 0 else ""
    if as_percent:
        return f"{sign}{delta:+.1%}"
    return f"{sign}{delta:+.2f}"


def diff_metrics(before_metrics: Dict[str, Any], after_metrics: Dict[str, Any]) -> List[str]:
    """Compare evaluation metrics between two snapshots."""
    lines = ["## Evaluation Metrics"]
    lines.append("-" * 80)

    # Key metrics to compare
    key_metrics = [
        ("total", "Total queries"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("pass_rate", "Pass rate", True),
        ("refusal_accuracy", "Refusal accuracy", True),
        ("hallucination_rate", "Hallucination rate", True),
        ("domain_accuracy", "Domain accuracy", True),
        ("avg_elapsed_s", "Avg latency (s)"),
    ]

    for key in key_metrics:
        if len(key) == 2:
            metric_key, label = key
            as_percent = False
        else:
            metric_key, label, as_percent = key

        if metric_key not in before_metrics or metric_key not in after_metrics:
            continue

        before_val = before_metrics[metric_key]
        after_val = after_metrics[metric_key]

        delta_str = format_delta(before_val, after_val, as_percent)
        lines.append(f"  {label:30} {before_val:8.2f} → {after_val:8.2f} ({delta_str})")

    # Intent method metrics
    if "intent_method_metrics" in before_metrics and "intent_method_metrics" in after_metrics:
        lines.append("\n## Intent Method Accuracy")
        lines.append("-" * 80)
        for method in ["rules", "v2_model"]:
            if method in before_metrics["intent_method_metrics"] and method in after_metrics["intent_method_metrics"]:
                before_acc = before_metrics["intent_method_metrics"][method]["accuracy"]
                after_acc = after_metrics["intent_method_metrics"][method]["accuracy"]
                delta_str = format_delta(before_acc, after_acc, True)
                lines.append(f"  {method:10} {before_acc:6.2%} → {after_acc:6.2%} ({delta_str})")

    # Intent type metrics
    if "intent_type_metrics" in before_metrics and "intent_type_metrics" in after_metrics:
        lines.append("\n## Intent Type Accuracy")
        lines.append("-" * 80)
        all_intents = set(before_metrics["intent_type_metrics"].keys()) | set(after_metrics["intent_type_metrics"].keys())
        for intent in sorted(all_intents):
            if intent in before_metrics["intent_type_metrics"] and intent in after_metrics["intent_type_metrics"]:
                before_acc = before_metrics["intent_type_metrics"][intent]["accuracy"]
                after_acc = after_metrics["intent_type_metrics"][intent]["accuracy"]
                delta_str = format_delta(before_acc, after_acc, True)
                lines.append(f"  {intent:10} {before_acc:6.2%} → {after_acc:6.2%} ({delta_str})")

    return lines


def diff_drift(before_drift: List[Dict[str, Any]], after_drift: List[Dict[str, Any]]) -> List[str]:
    """Compare drift detection results between two snapshots."""
    lines = ["## Drift Detection"]
    lines.append("-" * 80)

    before_topics = {d["topic"]: d for d in before_drift}
    after_topics = {d["topic"]: d for d in after_drift}

    all_topics = set(before_topics.keys()) | set(after_topics.keys())

    # New topics (only in after)
    new_topics = sorted(all_topics - before_topics.keys())
    if new_topics:
        lines.append("\n### New Topics (appeared in after)")
        for topic in new_topics:
            d = after_topics[topic]
            lines.append(f"  {topic:20} drift={d['drift_score']:.2f} misses={d['miss_count']}/{d['query_count']} action={d['action']}")

    # Removed topics (only in before)
    removed_topics = sorted(all_topics - after_topics.keys())
    if removed_topics:
        lines.append("\n### Removed Topics (disappeared in after)")
        for topic in removed_topics:
            d = before_topics[topic]
            lines.append(f"  {topic:20} drift={d['drift_score']:.2f} misses={d['miss_count']}/{d['query_count']} action={d['action']}")

    # Changed topics (in both, but different drift scores or actions)
    common_topics = sorted(before_topics.keys() & after_topics.keys())
    changed_topics = []
    for topic in common_topics:
        before_d = before_topics[topic]
        after_d = after_topics[topic]
        if (before_d["drift_score"] != after_d["drift_score"] or
            before_d["miss_count"] != after_d["miss_count"] or
            before_d["action"] != after_d["action"]):
            changed_topics.append((topic, before_d, after_d))

    if changed_topics:
        lines.append("\n### Changed Topics")
        for topic, before_d, after_d in changed_topics:
            drift_delta = format_delta(before_d["drift_score"], after_d["drift_score"])
            miss_delta = format_delta(before_d["miss_count"], after_d["miss_count"])
            action_change = f" (action: {before_d['action']} → {after_d['action']})" if before_d["action"] != after_d["action"] else ""
            lines.append(f"  {topic:20} drift={before_d['drift_score']:.2f} → {after_d['drift_score']:.2f} ({drift_delta}) "
                        f"misses={before_d['miss_count']}/{before_d['query_count']} → {after_d['miss_count']}/{after_d['query_count']} ({miss_delta}){action_change}")

    if not new_topics and not removed_topics and not changed_topics:
        lines.append("\n  No changes in drift detection.")

    return lines


def diff_alerts(before_alerts: List[Dict[str, Any]], after_alerts: List[Dict[str, Any]]) -> List[str]:
    """Compare alerts between two snapshots."""
    lines = ["## Alerts"]
    lines.append("-" * 80)

    before_alerts_by_topic = {a["topic"]: a for a in before_alerts}
    after_alerts_by_topic = {a["topic"]: a for a in after_alerts}

    all_topics = set(before_alerts_by_topic.keys()) | set(after_alerts_by_topic.keys())

    # New alerts
    new_alerts = sorted(all_topics - before_alerts_by_topic.keys())
    if new_alerts:
        lines.append("\n### New Alerts")
        for topic in new_alerts:
            a = after_alerts_by_topic[topic]
            lines.append(f"  {topic:20} type={a['type']:12} priority={a['priority']:8} action={a['action']}")

    # Resolved alerts
    resolved_alerts = sorted(all_topics - after_alerts_by_topic.keys())
    if resolved_alerts:
        lines.append("\n### Resolved Alerts")
        for topic in resolved_alerts:
            a = before_alerts_by_topic[topic]
            lines.append(f"  {topic:20} type={a['type']:12} priority={a['priority']:8} action={a['action']}")

    # Changed alerts
    common_topics = sorted(before_alerts_by_topic.keys() & after_alerts_by_topic.keys())
    changed_alerts = []
    for topic in common_topics:
        before_a = before_alerts_by_topic[topic]
        after_a = after_alerts_by_topic[topic]
        if (before_a["type"] != after_a["type"] or
            before_a["priority"] != after_a["priority"] or
            before_a["action"] != after_a["action"]):
            changed_alerts.append((topic, before_a, after_a))

    if changed_alerts:
        lines.append("\n### Changed Alerts")
        for topic, before_a, after_a in changed_alerts:
            type_change = f" (type: {before_a['type']} → {after_a['type']})" if before_a["type"] != after_a["type"] else ""
            priority_change = f" (priority: {before_a['priority']} → {after_a['priority']})" if before_a["priority"] != after_a["priority"] else ""
            action_change = f" (action: {before_a['action']} → {after_a['action']})" if before_a["action"] != after_a["action"] else ""
            lines.append(f"  {topic:20} {type_change}{priority_change}{action_change}")

    if not new_alerts and not resolved_alerts and not changed_alerts:
        lines.append("\n  No changes in alerts.")

    return lines


def diff_gate_decision(before_eval: Dict[str, Any], after_eval: Dict[str, Any]) -> List[str]:
    """Compare gate decisions between two snapshots."""
    lines = ["## Gate Decision"]
    lines.append("-" * 80)

    before_decision = before_eval.get("decision", "UNKNOWN")
    after_decision = after_eval.get("decision", "UNKNOWN")

    if before_decision == after_decision:
        lines.append(f"  Gate decision unchanged: {after_decision}")
    else:
        lines.append(f"  Gate decision changed: {before_decision} → {after_decision}")

    # Check for new failures
    before_failures = set(before_eval.get("failed_checks", []))
    after_failures = set(after_eval.get("failed_checks", []))

    new_failures = after_failures - before_failures
    resolved_failures = before_failures - after_failures

    if new_failures:
        lines.append("\n### New Failed Checks")
        for failure in sorted(new_failures):
            lines.append(f"  - {failure}")

    if resolved_failures:
        lines.append("\n### Resolved Failed Checks")
        for failure in sorted(resolved_failures):
            lines.append(f"  - {failure}")

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two snapshot directories")
    parser.add_argument("--before", required=True, help="Before snapshot directory (e.g., reports/before)")
    parser.add_argument("--after", required=True, help="After snapshot directory (e.g., reports/after)")
    args = parser.parse_args()

    before_dir = Path(args.before)
    after_dir = Path(args.after)

    if not before_dir.exists():
        print(f"Error: {before_dir} does not exist")
        return 1

    if not after_dir.exists():
        print(f"Error: {after_dir} does not exist")
        return 1

    # Load snapshot files
    try:
        before_eval = load_json(before_dir / "eval_strict.json")
        before_drift = load_json(before_dir / "drift.json")
        before_alerts = load_json(before_dir / "alerts.json")

        after_eval = load_json(after_dir / "eval_strict.json")
        after_drift = load_json(after_dir / "drift.json")
        after_alerts = load_json(after_dir / "alerts.json")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    # Generate diff report
    output_lines = []
    output_lines.append(f"# Snapshot Diff: {before_dir.name} → {after_dir.name}")
    output_lines.append("")

    # Gate decision
    output_lines.extend(diff_gate_decision(before_eval, after_eval))
    output_lines.append("")

    # Metrics
    output_lines.extend(diff_metrics(before_eval["metrics"], after_eval["metrics"]))
    output_lines.append("")

    # Drift
    output_lines.extend(diff_drift(before_drift, after_drift))
    output_lines.append("")

    # Alerts
    output_lines.extend(diff_alerts(before_alerts, after_alerts))

    # Print report
    print("\n".join(output_lines))

    return 0


if __name__ == "__main__":
    exit(main())
