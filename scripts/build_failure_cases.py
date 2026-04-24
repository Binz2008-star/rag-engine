"""Build failure_cases.jsonl from shadow evaluation report.

This script extracts failure cases from the shadow evaluation report,
filtering for low-confidence and mid-confidence uncertain predictions
that were not hard-rule bypasses.
"""

import json
import sys
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_report(report_path: Path) -> dict:
    """Load shadow evaluation report."""
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def extract_failure_rows(report: dict, report_path: Path) -> list[dict]:
    """Extract failure rows from report.
    
    Args:
        report: Shadow evaluation report dict
        report_path: Path to the report file (for metadata)
        
    Returns:
        List of failure case dicts with deduplication applied
    """
    failure_rows = []
    
    # Extract from curated_queries (higher priority for dedup)
    curated_rows = report.get("curated_queries", {}).get("rows", [])
    for row in curated_rows:
        if (
            not row.get("skipped_hard_rule", False)
            and row.get("shadow_reason") in {"low_confidence", "mid_confidence_uncertain"}
        ):
            failure_rows.append({
                "query": row["query"],
                "label": row["expected_intent"],
                "label_source": "expected_intent",
                "source_dataset": "curated_queries",
                "suite": row.get("suite"),
                "shadow_reason": row["shadow_reason"],
                "shadow_intent": row["shadow_intent"],
                "shadow_confidence": row["shadow_confidence"],
                "public_intent": row["public_intent"],
                "public_disagreement": row["public_disagreement"],
                "report_path": str(report_path),
            })
    
    # Extract from train_labeled (lower priority for dedup)
    train_rows = report.get("train_labeled", {}).get("rows", [])
    for row in train_rows:
        if (
            not row.get("skipped_hard_rule", False)
            and row.get("shadow_reason") in {"low_confidence", "mid_confidence_uncertain"}
        ):
            failure_rows.append({
                "query": row["query"],
                "label": row["expected_intent"],
                "label_source": "expected_intent",
                "source_dataset": "train_labeled",
                "suite": row.get("suite"),
                "shadow_reason": row["shadow_reason"],
                "shadow_intent": row["shadow_intent"],
                "shadow_confidence": row["shadow_confidence"],
                "public_intent": row["public_intent"],
                "public_disagreement": row["public_disagreement"],
                "report_path": str(report_path),
            })
    
    # Dedupe by (query.casefold().strip(), label)
    # Prefer curated_queries over train_labeled
    seen = {}
    deduped = []
    for row in failure_rows:
        key = (row["query"].casefold().strip(), row["label"])
        if key not in seen:
            seen[key] = row
            deduped.append(row)
        else:
            # If duplicate exists, prefer curated_queries
            existing = seen[key]
            if row["source_dataset"] == "curated_queries" and existing["source_dataset"] == "train_labeled":
                seen[key] = row
                # Replace in deduped list
                idx = deduped.index(existing)
                deduped[idx] = row
    
    return deduped


def write_jsonl(output_path: Path, rows: list[dict]) -> None:
    """Write rows to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main():
    """Build failure_cases.jsonl from shadow evaluation report."""
    report_path = Path("reports/shadow_eval.json")
    output_path = Path("data/failure_cases.jsonl")
    
    if not report_path.exists():
        print(f"Error: {report_path} not found")
        sys.exit(1)
    
    # Load report
    report = load_report(report_path)
    
    # Extract failure rows
    failure_rows = extract_failure_rows(report, report_path)
    
    # Write to JSONL
    write_jsonl(output_path, failure_rows)
    
    # Print summary
    print(f"Extracted {len(failure_rows)} failure cases")
    
    # Counts by source_dataset
    source_counts = {}
    for row in failure_rows:
        source = row["source_dataset"]
        source_counts[source] = source_counts.get(source, 0) + 1
    print(f"By source_dataset: {source_counts}")
    
    # Counts by shadow_reason
    reason_counts = {}
    for row in failure_rows:
        reason = row["shadow_reason"]
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    print(f"By shadow_reason: {reason_counts}")
    
    print(f"Output: {output_path}")
    
    # Exit with success
    sys.exit(0)


if __name__ == "__main__":
    main()
