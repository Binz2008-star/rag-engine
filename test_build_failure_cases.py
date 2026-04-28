"""Test build_failure_cases.py with synthetic fixtures."""

import json
import tempfile
from pathlib import Path

from scripts.build_failure_cases import extract_failure_rows, load_report, write_jsonl


def test_load_report():
    """Test loading report from JSON file."""
    # Create temp report file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
        report_data = {
            "metadata": {"total_rows": 10},
            "train_labeled": {"rows": []},
            "curated_queries": {"rows": []},
        }
        json.dump(report_data, f)
    
    try:
        report = load_report(temp_path)
        assert report["metadata"]["total_rows"] == 10
    finally:
        temp_path.unlink()


def test_extract_failure_rows_filters_hard_rule():
    """Test that hard-rule rows are filtered out."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is roben's role?",
                    "expected_intent": "cv",
                    "skipped_hard_rule": True,
                    "shadow_reason": "hard_rule_bypass",
                    "shadow_intent": None,
                    "shadow_confidence": 0.0,
                    "public_intent": "cv",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert len(failure_rows) == 0


def test_extract_failure_rows_filters_invalid_shadow_reason():
    """Test that rows with invalid shadow_reason are filtered out."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "model_unavailable",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.0,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": None,
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert len(failure_rows) == 0


def test_extract_failure_rows_keeps_low_confidence():
    """Test that low_confidence rows are kept."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert len(failure_rows) == 1
    assert failure_rows[0]["shadow_reason"] == "low_confidence"


def test_extract_failure_rows_keeps_mid_confidence_uncertain():
    """Test that mid_confidence_uncertain rows are kept."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "mid_confidence_uncertain",
                    "shadow_intent": "uncertain",
                    "shadow_confidence": 0.7,
                    "public_intent": "general",
                    "public_disagreement": True,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert len(failure_rows) == 1
    assert failure_rows[0]["shadow_reason"] == "mid_confidence_uncertain"


def test_extract_failure_rows_dedupe_casefold():
    """Test deduplication by query.casefold().strip() and label."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
                {
                    "query": "WHAT IS GDP?",  # Same query, different case
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    # Should dedupe to 1 row
    assert len(failure_rows) == 1


def test_extract_failure_rows_dedupe_priority_curated_over_train():
    """Test that curated_queries rows take priority over train_labeled on duplicates."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "mid_confidence_uncertain",
                    "shadow_intent": "uncertain",
                    "shadow_confidence": 0.7,
                    "public_intent": "general",
                    "public_disagreement": True,
                    "suite": None,
                },
            ]
        },
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    # Should dedupe to 1 row, with curated_queries source
    assert len(failure_rows) == 1
    assert failure_rows[0]["source_dataset"] == "curated_queries"
    assert failure_rows[0]["shadow_reason"] == "low_confidence"


def test_extract_failure_rows_schema():
    """Test that output rows have correct schema."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    row = failure_rows[0]
    assert "query" in row
    assert "label" in row
    assert "label_source" in row
    assert "source_dataset" in row
    assert "suite" in row
    assert "shadow_reason" in row
    assert "shadow_intent" in row
    assert "shadow_confidence" in row
    assert "public_intent" in row
    assert "public_disagreement" in row
    assert "report_path" in row


def test_extract_failure_rows_uses_expected_intent_as_label():
    """Test that expected_intent is used as label."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {"rows": []},
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert failure_rows[0]["label"] == "general"
    assert failure_rows[0]["label_source"] == "expected_intent"


def test_write_jsonl():
    """Test writing rows to JSONL file."""
    rows = [
        {"query": "What is GDP?", "label": "general"},
        {"query": "What is ECO?", "label": "eco"},
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        write_jsonl(temp_path, rows)
        
        # Verify file contents
        with open(temp_path, encoding="utf-8") as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        assert json.loads(lines[0])["query"] == "What is GDP?"
        assert json.loads(lines[1])["query"] == "What is ECO?"
    finally:
        temp_path.unlink()


def test_extract_failure_rows_from_both_datasets():
    """Test extracting from both curated_queries and train_labeled."""
    report = {
        "curated_queries": {
            "rows": [
                {
                    "query": "What is GDP?",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.5,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": "baseline",
                },
            ]
        },
        "train_labeled": {
            "rows": [
                {
                    "query": "Hello",
                    "expected_intent": "general",
                    "skipped_hard_rule": False,
                    "shadow_reason": "low_confidence",
                    "shadow_intent": "general",
                    "shadow_confidence": 0.4,
                    "public_intent": "general",
                    "public_disagreement": False,
                    "suite": None,
                },
            ]
        },
    }
    
    report_path = Path("reports/shadow_eval.json")
    failure_rows = extract_failure_rows(report, report_path)
    
    assert len(failure_rows) == 2
    source_datasets = {row["source_dataset"] for row in failure_rows}
    assert "curated_queries" in source_datasets
    assert "train_labeled" in source_datasets


if __name__ == "__main__":
    # Run tests
    test_load_report()
    print("✓ test_load_report")
    
    test_extract_failure_rows_filters_hard_rule()
    print("✓ test_extract_failure_rows_filters_hard_rule")
    
    test_extract_failure_rows_filters_invalid_shadow_reason()
    print("✓ test_extract_failure_rows_filters_invalid_shadow_reason")
    
    test_extract_failure_rows_keeps_low_confidence()
    print("✓ test_extract_failure_rows_keeps_low_confidence")
    
    test_extract_failure_rows_keeps_mid_confidence_uncertain()
    print("✓ test_extract_failure_rows_keeps_mid_confidence_uncertain")
    
    test_extract_failure_rows_dedupe_casefold()
    print("✓ test_extract_failure_rows_dedupe_casefold")
    
    test_extract_failure_rows_dedupe_priority_curated_over_train()
    print("✓ test_extract_failure_rows_dedupe_priority_curated_over_train")
    
    test_extract_failure_rows_schema()
    print("✓ test_extract_failure_rows_schema")
    
    test_extract_failure_rows_uses_expected_intent_as_label()
    print("✓ test_extract_failure_rows_uses_expected_intent_as_label")
    
    test_write_jsonl()
    print("✓ test_write_jsonl")
    
    test_extract_failure_rows_from_both_datasets()
    print("✓ test_extract_failure_rows_from_both_datasets")
    
    print("\nAll build_failure_cases tests passed!")
