"""Test review_failure_cases.py with synthetic fixtures."""

import json
import tempfile
from pathlib import Path

from scripts.review_failure_cases import load_failure_cases, transform_row, validate_row, write_seed_jsonl


def test_load_failure_cases():
    """Test loading failure cases from JSONL file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"query": "What is GDP?", "label": "general"}\n')
        f.write('{"query": "What is ECO?", "label": "eco"}\n')
    
    try:
        rows = load_failure_cases(temp_path)
        assert len(rows) == 2
        assert rows[0]["query"] == "What is GDP?"
        assert rows[1]["label"] == "eco"
    finally:
        temp_path.unlink()


def test_load_failure_cases_missing_file():
    """Test that missing file raises FileNotFoundError."""
    temp_path = Path("nonexistent.jsonl")
    try:
        load_failure_cases(temp_path)
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_load_failure_cases_invalid_json():
    """Test that invalid JSON raises JSONDecodeError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"query": "What is GDP?", "label": "general"}\n')
        f.write('invalid json\n')
    
    try:
        load_failure_cases(temp_path)
        assert False, "Should have raised JSONDecodeError"
    except json.JSONDecodeError:
        pass
    finally:
        temp_path.unlink()


def test_validate_row_valid_label():
    """Test validation with valid labels."""
    for label in ["cv", "eco", "general"]:
        row = {"query": "What is GDP?", "label": label}
        assert validate_row(row) is True


def test_validate_row_invalid_label():
    """Test validation with invalid label."""
    row = {"query": "What is GDP?", "label": "invalid"}
    try:
        validate_row(row)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid label" in str(e)


def test_validate_row_blank_query():
    """Test validation with blank query."""
    row = {"query": "", "label": "general"}
    try:
        validate_row(row)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "non-empty" in str(e)


def test_validate_row_whitespace_query():
    """Test validation with whitespace-only query."""
    row = {"query": "   ", "label": "general"}
    try:
        validate_row(row)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "non-empty" in str(e)


def test_validate_row_missing_query():
    """Test validation with missing query."""
    row = {"label": "general"}
    try:
        validate_row(row)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "non-empty" in str(e)


def test_transform_row():
    """Test row transformation to seed format."""
    row = {
        "query": "What is GDP?",
        "label": "general",
        "shadow_reason": "low_confidence",
    }
    transformed = transform_row(row)
    
    assert transformed["query"] == "What is GDP?"
    assert transformed["label"] == "general"
    assert transformed["source"] == "failure_case_review"
    assert transformed["reviewed"] is False


def test_transform_row_fixed_source():
    """Test that source is always fixed to 'failure_case_review'."""
    row = {"query": "What is GDP?", "label": "general"}
    transformed = transform_row(row)
    assert transformed["source"] == "failure_case_review"


def test_transform_row_fixed_reviewed_false():
    """Test that reviewed is always False."""
    row = {"query": "What is GDP?", "label": "general"}
    transformed = transform_row(row)
    assert transformed["reviewed"] is False


def test_write_seed_jsonl():
    """Test writing seed rows to JSONL file."""
    rows = [
        {"query": "What is GDP?", "label": "general", "source": "failure_case_review", "reviewed": False},
        {"query": "What is ECO?", "label": "eco", "source": "failure_case_review", "reviewed": False},
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        write_seed_jsonl(temp_path, rows)
        
        # Verify file contents
        with open(temp_path, encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        row1 = json.loads(lines[0])
        assert row1["query"] == "What is GDP?"
        assert row1["source"] == "failure_case_review"
        assert row1["reviewed"] is False
    finally:
        temp_path.unlink()


def test_order_preservation():
    """Test that input order is preserved in output."""
    rows = [
        {"query": "First", "label": "cv"},
        {"query": "Second", "label": "eco"},
        {"query": "Third", "label": "general"},
    ]
    
    transformed = [transform_row(row) for row in rows]
    
    assert transformed[0]["query"] == "First"
    assert transformed[1]["query"] == "Second"
    assert transformed[2]["query"] == "Third"


def test_label_counts():
    """Test that label counts are tracked correctly."""
    rows = [
        {"query": "Q1", "label": "cv"},
        {"query": "Q2", "label": "cv"},
        {"query": "Q3", "label": "eco"},
        {"query": "Q4", "label": "general"},
    ]
    
    label_counts = {"cv": 0, "eco": 0, "general": 0}
    for row in rows:
        validate_row(row)
        transformed = transform_row(row)
        label_counts[transformed["label"]] += 1
    
    assert label_counts == {"cv": 2, "eco": 1, "general": 1}


def test_output_shape():
    """Test that output has correct shape."""
    row = {"query": "What is GDP?", "label": "general"}
    transformed = transform_row(row)
    
    assert "query" in transformed
    assert "label" in transformed
    assert "source" in transformed
    assert "reviewed" in transformed
    assert len(transformed) == 4


if __name__ == "__main__":
    # Run tests
    test_load_failure_cases()
    print("✓ test_load_failure_cases")
    
    test_load_failure_cases_missing_file()
    print("✓ test_load_failure_cases_missing_file")
    
    test_load_failure_cases_invalid_json()
    print("✓ test_load_failure_cases_invalid_json")
    
    test_validate_row_valid_label()
    print("✓ test_validate_row_valid_label")
    
    test_validate_row_invalid_label()
    print("✓ test_validate_row_invalid_label")
    
    test_validate_row_blank_query()
    print("✓ test_validate_row_blank_query")
    
    test_validate_row_whitespace_query()
    print("✓ test_validate_row_whitespace_query")
    
    test_validate_row_missing_query()
    print("✓ test_validate_row_missing_query")
    
    test_transform_row()
    print("✓ test_transform_row")
    
    test_transform_row_fixed_source()
    print("✓ test_transform_row_fixed_source")
    
    test_transform_row_fixed_reviewed_false()
    print("✓ test_transform_row_fixed_reviewed_false")
    
    test_write_seed_jsonl()
    print("✓ test_write_seed_jsonl")
    
    test_order_preservation()
    print("✓ test_order_preservation")
    
    test_label_counts()
    print("✓ test_label_counts")
    
    test_output_shape()
    print("✓ test_output_shape")
    
    print("\nAll review_failure_cases tests passed!")
