"""Review failure cases and create train_v2_seed.jsonl.

This script reads failure_cases.jsonl and outputs a seed dataset
for human review, with validation on labels and queries.
"""

import json
import sys
from pathlib import Path

# Add repo root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

VALID_LABELS = {"cv", "eco", "general"}


def load_failure_cases(input_path: Path) -> list[dict]:
    """Load failure cases from JSONL file.
    
    Args:
        input_path: Path to failure_cases.jsonl
        
    Returns:
        List of failure case dicts
        
    Raises:
        FileNotFoundError: If input file does not exist
        json.JSONDecodeError: If JSON is invalid
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    rows = []
    with open(input_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    row = json.loads(line)
                    rows.append(row)
                except json.JSONDecodeError as e:
                    raise json.JSONDecodeError(
                        f"Invalid JSON at line {line_num}: {e.msg}",
                        e.doc,
                        e.pos,
                    )
    return rows


def validate_row(row: dict) -> bool:
    """Validate a failure case row.
    
    Args:
        row: Failure case dict
        
    Returns:
        True if valid, False otherwise
        
    Raises:
        ValueError: If label is invalid or query is blank
    """
    # Validate label
    label = row.get("label")
    if label not in VALID_LABELS:
        raise ValueError(f"Invalid label '{label}'. Must be one of: {VALID_LABELS}")
    
    # Validate query
    query = row.get("query", "")
    if not query or not query.strip():
        raise ValueError("Query must exist and be non-empty after strip")
    
    return True


def transform_row(row: dict) -> dict:
    """Transform failure case row to seed format.
    
    Args:
        row: Failure case dict
        
    Returns:
        Transformed dict with query, label, source, reviewed fields
    """
    return {
        "query": row["query"],
        "label": row["label"],
        "source": "failure_case_review",
        "reviewed": False,
    }


def write_seed_jsonl(output_path: Path, rows: list[dict]) -> None:
    """Write rows to JSONL file.
    
    Args:
        output_path: Path to output file
        rows: List of row dicts to write
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def main():
    """Review failure cases and create train_v2_seed.jsonl."""
    input_path = Path("data/failure_cases.jsonl")
    output_path = Path("data/train_v2_seed.jsonl")
    
    # Load failure cases
    try:
        failure_cases = load_failure_cases(input_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Validate and transform rows
    seed_rows = []
    label_counts = {label: 0 for label in VALID_LABELS}
    
    for row in failure_cases:
        try:
            validate_row(row)
            transformed = transform_row(row)
            seed_rows.append(transformed)
            label_counts[transformed["label"]] += 1
        except ValueError as e:
            print(f"Error: {e} in row: {row}")
            sys.exit(1)
    
    # Write seed file
    write_seed_jsonl(output_path, seed_rows)
    
    # Print summary
    print(f"Rows written: {len(seed_rows)}")
    print(f"Counts by label: {label_counts}")
    print(f"Output: {output_path}")
    
    # Exit with success
    sys.exit(0)


if __name__ == "__main__":
    main()
