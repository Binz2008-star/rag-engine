#!/usr/bin/env python3
"""
Validation script for train_v2_human.jsonl dataset.

Schema:
- query: str (non-empty)
- label: str (one of: cv, eco, general)
- label_source: str (one of: failure_case_review, existing_labeled_seed, manual_expansion)
- reviewed: bool (must be true)

Validation rules:
- Required keys present
- Query non-empty
- Label valid
- Label source valid
- Reviewed must be true
- No duplicate normalized queries (casefold().strip())
- Conflicting duplicate labels fail
- Hard minimum: 100 total rows and at least 30 per class
- Exit non-zero if hard gate fails
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict


ALLOWED_LABELS = {"cv", "eco", "general"}
ALLOWED_LABEL_SOURCES = {"failure_case_review", "existing_labeled_seed", "manual_expansion"}
REQUIRED_KEYS = {"query", "label", "label_source", "reviewed"}
MIN_TOTAL_ROWS = 100
MIN_ROWS_PER_CLASS = 30


def validate_dataset(file_path: Path) -> bool:
    """
    Validate train_v2_human.jsonl dataset.

    Returns:
        bool: True if validation passes, False otherwise
    """
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        return False

    rows = []
    errors = []
    warnings = []

    # Read and parse all rows
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                row = json.loads(line)
                rows.append((line_num, row))
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: Invalid JSON - {e}")

    if not rows:
        errors.append("ERROR: No valid rows found in dataset")
        print_errors(errors)
        return False

    # Validate each row
    normalized_queries = {}
    for line_num, row in rows:
        # Check required keys
        missing_keys = REQUIRED_KEYS - row.keys()
        if missing_keys:
            errors.append(f"Line {line_num}: Missing required keys: {missing_keys}")
            continue

        # Validate query
        query = row["query"]
        if not isinstance(query, str) or not query.strip():
            errors.append(f"Line {line_num}: Query must be non-empty string")
            continue

        # Validate label
        label = row["label"]
        if label not in ALLOWED_LABELS:
            errors.append(f"Line {line_num}: Invalid label '{label}'. Allowed: {ALLOWED_LABELS}")
            continue

        # Validate label_source
        label_source = row["label_source"]
        if label_source not in ALLOWED_LABEL_SOURCES:
            errors.append(f"Line {line_num}: Invalid label_source '{label_source}'. Allowed: {ALLOWED_LABEL_SOURCES}")
            continue

        # Validate reviewed
        reviewed = row["reviewed"]
        if not isinstance(reviewed, bool) or not reviewed:
            errors.append(f"Line {line_num}: reviewed must be true (got {reviewed})")
            continue

        # Check for duplicate normalized queries
        normalized = query.casefold().strip()
        if normalized in normalized_queries:
            existing_line, existing_label = normalized_queries[normalized]
            errors.append(
                f"Line {line_num}: Duplicate query. "
                f"Line {existing_line} has label '{existing_label}', "
                f"line {line_num} has label '{label}'"
            )
        else:
            normalized_queries[normalized] = (line_num, label)

    # Print errors and warnings
    print_errors(errors)
    print_warnings(warnings)

    if errors:
        return False

    # Count by label
    label_counts = Counter(row["label"] for _, row in rows)
    print("\n=== Label Counts ===")
    for label in sorted(ALLOWED_LABELS):
        count = label_counts.get(label, 0)
        print(f"{label}: {count}")
    print(f"Total: {len(rows)}")

    # Check hard minimums
    total_rows = len(rows)
    if total_rows < MIN_TOTAL_ROWS:
        errors.append(
            f"ERROR: Total rows ({total_rows}) below minimum ({MIN_TOTAL_ROWS})"
        )

    for label in ALLOWED_LABELS:
        count = label_counts.get(label, 0)
        if count < MIN_ROWS_PER_CLASS:
            errors.append(
                f"ERROR: Label '{label}' has {count} rows, below minimum ({MIN_ROWS_PER_CLASS})"
            )

    if errors:
        print_errors(errors)
        return False

    print("\n✓ Validation passed")
    return True


def print_errors(errors: list[str]) -> None:
    """Print all errors."""
    if errors:
        print("\n=== ERRORS ===")
        for error in errors:
            print(error)


def print_warnings(warnings: list[str]) -> None:
    """Print all warnings."""
    if warnings:
        print("\n=== WARNINGS ===")
        for warning in warnings:
            print(warning)


def main() -> int:
    """Main entry point."""
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        file_path = Path(__file__).parent.parent / "data" / "train_v2_human.jsonl"

    success = validate_dataset(file_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
