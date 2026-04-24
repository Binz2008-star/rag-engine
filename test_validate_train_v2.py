#!/usr/bin/env python3
"""
Tests for validate_train_v2.py script.
"""

import json
import subprocess
import tempfile
from pathlib import Path


def run_validator(file_path: Path) -> tuple[int, str, str]:
    """Run the validator and return exit code, stdout, stderr."""
    result = subprocess.run(
        ["python", "scripts/validate_train_v2.py", str(file_path)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_valid_dataset_passes():
    """Test that a valid dataset passes validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write 100 rows with balanced labels (34 cv, 33 eco, 33 general)
        for i in range(34):
            f.write(json.dumps({
                "query": f"What is Robin's skill {i}?",
                "label": "cv",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(33):
            f.write(json.dumps({
                "query": f"What is Eco service {i}?",
                "label": "eco",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(33):
            f.write(json.dumps({
                "query": f"What is general fact {i}?",
                "label": "general",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code == 0, f"Expected exit code 0, got {exit_code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "✓ Validation passed" in stdout
        assert "cv: 34" in stdout
        assert "eco: 33" in stdout
        assert "general: 33" in stdout
        assert "Total: 100" in stdout
        print("✓ test_valid_dataset_passes passed")
    finally:
        temp_path.unlink()


def test_invalid_label_fails():
    """Test that an invalid label fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "invalid_label",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Invalid label 'invalid_label'" in stdout
        print("✓ test_invalid_label_fails passed")
    finally:
        temp_path.unlink()


def test_missing_key_fails():
    """Test that missing required key fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "manual_expansion"
            # Missing "reviewed"
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Missing required keys" in stdout
        print("✓ test_missing_key_fails passed")
    finally:
        temp_path.unlink()


def test_blank_query_fails():
    """Test that blank query fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "",
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Query must be non-empty" in stdout
        print("✓ test_blank_query_fails passed")
    finally:
        temp_path.unlink()


def test_duplicate_query_fails():
    """Test that duplicate query with different labels fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        f.write(json.dumps({
            "query": "What is Robin's skill?",  # Same query
            "label": "eco",  # Different label
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Duplicate query" in stdout
        print("✓ test_duplicate_query_fails passed")
    finally:
        temp_path.unlink()


def test_duplicate_query_same_label_fails():
    """Test that duplicate query with same label fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        f.write(json.dumps({
            "query": "What is Robin's skill?",  # Same query, same label
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Duplicate query" in stdout
        print("✓ test_duplicate_query_same_label_fails passed")
    finally:
        temp_path.unlink()


def test_invalid_label_source_fails():
    """Test that invalid label_source fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "invalid_source",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Invalid label_source 'invalid_source'" in stdout
        print("✓ test_invalid_label_source_fails passed")
    finally:
        temp_path.unlink()


def test_reviewed_false_fails():
    """Test that reviewed=false fails validation."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": False
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "reviewed must be true" in stdout
        print("✓ test_reviewed_false_fails passed")
    finally:
        temp_path.unlink()


def test_hard_minimum_total_fails():
    """Test that dataset with less than 100 total rows fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write only 99 rows
        for i in range(33):
            f.write(json.dumps({
                "query": f"What is Robin's skill {i}?",
                "label": "cv",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(33):
            f.write(json.dumps({
                "query": f"What is Eco service {i}?",
                "label": "eco",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(33):
            f.write(json.dumps({
                "query": f"What is general fact {i}?",
                "label": "general",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Total rows (99) below minimum (100)" in stdout
        print("✓ test_hard_minimum_total_fails passed")
    finally:
        temp_path.unlink()


def test_hard_minimum_per_class_fails():
    """Test that dataset with less than 30 rows per class fails."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write 100 rows but only 29 cv
        for i in range(29):
            f.write(json.dumps({
                "query": f"What is Robin's skill {i}?",
                "label": "cv",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(35):
            f.write(json.dumps({
                "query": f"What is Eco service {i}?",
                "label": "eco",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(36):
            f.write(json.dumps({
                "query": f"What is general fact {i}?",
                "label": "general",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Label 'cv' has 29 rows, below minimum (30)" in stdout
        print("✓ test_hard_minimum_per_class_fails passed")
    finally:
        temp_path.unlink()


def test_case_insensitive_duplicate_detection():
    """Test that duplicate detection is case-insensitive."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "query": "What is Robin's skill?",
            "label": "cv",
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        f.write(json.dumps({
            "query": "WHAT IS ROBIN'S SKILL?",  # Same query, different case
            "label": "eco",  # Different label
            "label_source": "manual_expansion",
            "reviewed": True
        }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code != 0, f"Expected non-zero exit code, got {exit_code}"
        assert "Duplicate query" in stdout
        print("✓ test_case_insensitive_duplicate_detection passed")
    finally:
        temp_path.unlink()


def test_counts_by_label_correct():
    """Test that label counts are reported correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write 105 rows with specific counts
        for i in range(35):
            f.write(json.dumps({
                "query": f"What is Robin's skill {i}?",
                "label": "cv",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(35):
            f.write(json.dumps({
                "query": f"What is Eco service {i}?",
                "label": "eco",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        for i in range(35):
            f.write(json.dumps({
                "query": f"What is general fact {i}?",
                "label": "general",
                "label_source": "manual_expansion",
                "reviewed": True
            }) + "\n")
        temp_path = Path(f.name)

    try:
        exit_code, stdout, stderr = run_validator(temp_path)
        assert exit_code == 0, f"Expected exit code 0, got {exit_code}\nstdout: {stdout}\nstderr: {stderr}"
        assert "cv: 35" in stdout
        assert "eco: 35" in stdout
        assert "general: 35" in stdout
        assert "Total: 105" in stdout
        print("✓ test_counts_by_label_correct passed")
    finally:
        temp_path.unlink()


def run_all_tests():
    """Run all tests."""
    print("Running tests for validate_train_v2.py...")
    print()

    test_valid_dataset_passes()
    test_invalid_label_fails()
    test_missing_key_fails()
    test_blank_query_fails()
    test_duplicate_query_fails()
    test_duplicate_query_same_label_fails()
    test_invalid_label_source_fails()
    test_reviewed_false_fails()
    test_hard_minimum_total_fails()
    test_hard_minimum_per_class_fails()
    test_case_insensitive_duplicate_detection()
    test_counts_by_label_correct()

    print()
    print("✓ All tests passed")


if __name__ == "__main__":
    run_all_tests()
