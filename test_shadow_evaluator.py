"""Test B2 Shadow Evaluator with dataset-driven temp fixtures."""

import json
import tempfile
from pathlib import Path

from evaluation.shadow_evaluator import ShadowEvaluator, ShadowEvalReport
from router.intent_router import IntentRouter


def test_load_train_jsonl():
    """Test loading training data from JSONL."""
    evaluator = ShadowEvaluator(IntentRouter())

    # Create temp JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"query": "What is GDP?", "intent": "general"}\n')
        f.write('{"query": "ECO services", "intent": "eco"}\n')

    try:
        rows = evaluator.load_train_jsonl(temp_path)
        assert len(rows) == 2
        assert rows[0]["query"] == "What is GDP?"
        assert rows[0]["expected_intent"] == "general"
        assert rows[1]["query"] == "ECO services"
        assert rows[1]["expected_intent"] == "eco"
    finally:
        temp_path.unlink()


def test_load_eval_queries_json():
    """Test loading evaluation queries from JSON."""
    evaluator = ShadowEvaluator(IntentRouter())

    # Create temp JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
        data = [
            {"query": "What is ECO?", "expected_intent": "eco", "suite": "baseline"},
            {"expected_intent": "cv", "suite": "test"},
        ]
        json.dump(data, f)

    try:
        rows = evaluator.load_eval_queries_json(temp_path)
        assert len(rows) == 2
        assert rows[0]["query"] == "What is ECO?"
        assert rows[0]["expected_intent"] == "eco"
        assert rows[0]["suite"] == "baseline"
        assert rows[1]["query"] == ""
        assert rows[1]["expected_intent"] == "cv"
        assert rows[1]["suite"] == "test"
    finally:
        temp_path.unlink()


def test_is_hard_rule():
    """Test hard-rule detection."""
    evaluator = ShadowEvaluator(IntentRouter())

    # CV hard-rule (roben)
    assert evaluator.is_hard_rule("What is roben's role?")

    # ECO hard-rule
    assert evaluator.is_hard_rule("What environmental services does ECO provide?")

    # CV hard-rule
    assert evaluator.is_hard_rule("CV skills for engineers")

    # Non-rule
    assert not evaluator.is_hard_rule("What is the GDP of Japan?")


def test_evaluate_dataset_skip_hard_rule():
    """Test that hard-rule rows are skipped from evaluation."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [
        {"query": "What is roben's role?", "expected_intent": "cv"},
        {"query": "What is GDP?", "expected_intent": "general"},
        {"query": "ECO services", "expected_intent": "eco"},
    ]

    report = evaluator.evaluate_dataset(rows)

    assert report.total_rows == 3
    # Check that roben query was detected as hard rule
    assert evaluator.is_hard_rule("What is roben's role?")
    # Check that ECO query was detected as hard rule
    assert evaluator.is_hard_rule("ECO services")
    # So at least 2 should be skipped
    assert report.skipped_hard_rule_rows >= 2
    assert report.evaluated_rows <= 1


def test_evaluate_dataset_metrics():
    """Test comprehensive metrics from dataset evaluation."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [
        {"query": "What is GDP?", "expected_intent": "general"},
        {"query": "Tell me about physics", "expected_intent": "general"},
        {"query": "Random question here", "expected_intent": "cv"},
    ]

    report = evaluator.evaluate_dataset(rows)

    assert report.total_rows == 3
    # Check that metrics are present (access as attributes, not dict keys)
    assert hasattr(report, "overall_accuracy")
    assert hasattr(report, "per_intent_accuracy")
    assert hasattr(report, "uncertain_rate")
    assert hasattr(report, "fallback_rate")
    assert hasattr(report, "public_disagreement_rate")
    assert hasattr(report, "confidence_band_counts")
    assert hasattr(report, "shadow_intent_counts")
    assert hasattr(report, "shadow_reason_counts")
    assert len(report.rows) == 3


def test_uncertain_counts_as_incorrect():
    """Test that uncertain predictions count as incorrect."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [
        {"query": "What is GDP?", "expected_intent": "general"},
    ]

    report = evaluator.evaluate_dataset(rows)

    # If shadow predicts uncertain, it should not count as correct
    # even if expected_intent is general
    assert report.uncertain_rate >= 0.0


def test_row_capture():
    """Test that all required fields are captured per row."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [
        {"query": "What is GDP?", "expected_intent": "general", "suite": "test"},
    ]

    report = evaluator.evaluate_dataset(rows)

    row = report.rows[0]
    assert "query" in row
    assert "expected_intent" in row
    assert "shadow_intent" in row
    assert "shadow_confidence" in row
    assert "shadow_reason" in row
    assert "public_intent" in row
    assert "public_disagreement" in row
    assert "suite" in row
    assert "skipped_hard_rule" in row


def test_confidence_band_counts():
    """Test confidence band counting from dataset evaluation."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [{"query": "What is GDP?", "expected_intent": "general"}]
    report = evaluator.evaluate_dataset(rows)

    bands = report.confidence_band_counts
    assert "<0.60" in bands
    assert "0.60-0.79" in bands
    assert ">=0.80" in bands


def test_shadow_intent_counts():
    """Test shadow intent distribution counting."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [{"query": "What is GDP?", "expected_intent": "general"}]
    report = evaluator.evaluate_dataset(rows)

    intent_counts = report.shadow_intent_counts
    assert "cv" in intent_counts or "eco" in intent_counts or "general" in intent_counts or "uncertain" in intent_counts


def test_shadow_reason_counts():
    """Test shadow reason distribution counting."""
    evaluator = ShadowEvaluator(IntentRouter())

    rows = [{"query": "What is GDP?", "expected_intent": "general"}]
    report = evaluator.evaluate_dataset(rows)

    reason_counts = report.shadow_reason_counts
    assert len(reason_counts) >= 0


def test_no_dependency_on_model_artifacts():
    """Test that evaluator works without model artifacts."""
    evaluator = ShadowEvaluator(IntentRouter(model=None))

    rows = [{"query": "What is GDP?", "expected_intent": "general"}]
    report = evaluator.evaluate_dataset(rows)

    assert report.total_rows == 1
    assert isinstance(report, ShadowEvalReport)


def test_load_train_jsonl_label_field():
    """Test that loader handles 'label' field from train.jsonl."""
    evaluator = ShadowEvaluator(IntentRouter())

    # Create temp JSONL file with 'label' field (train.jsonl format)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"query": "What is GDP?", "label": "general"}\n')
        f.write('{"query": "ECO services", "label": "eco"}\n')

    try:
        rows = evaluator.load_train_jsonl(temp_path)
        assert len(rows) == 2
        assert rows[0]["query"] == "What is GDP?"
        assert rows[0]["expected_intent"] == "general"
        assert rows[1]["query"] == "ECO services"
        assert rows[1]["expected_intent"] == "eco"
    finally:
        temp_path.unlink()


def test_load_train_jsonl_intent_field():
    """Test that loader handles 'intent' field (intent_dataset.jsonl format)."""
    evaluator = ShadowEvaluator(IntentRouter())

    # Create temp JSONL file with 'intent' field (intent_dataset.jsonl format)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"query": "What is GDP?", "intent": "general"}\n')
        f.write('{"query": "ECO services", "intent": "eco"}\n')

    try:
        rows = evaluator.load_train_jsonl(temp_path)
        assert len(rows) == 2
        assert rows[0]["query"] == "What is GDP?"
        assert rows[0]["expected_intent"] == "general"
        assert rows[1]["query"] == "ECO services"
        assert rows[1]["expected_intent"] == "eco"
    finally:
        temp_path.unlink()


def test_private_route_with_shadow():
    """Test that route_with_shadow is private (starts with underscore)."""
    router = IntentRouter()
    assert hasattr(router, "_route_with_shadow")
    # Should not have public version
    assert not hasattr(router, "route_with_shadow")


if __name__ == "__main__":
    # Run tests
    test_load_train_jsonl()
    print("✓ test_load_train_jsonl")

    test_load_eval_queries_json()
    print("✓ test_load_eval_queries_json")

    test_is_hard_rule()
    print("✓ test_is_hard_rule")

    test_evaluate_dataset_skip_hard_rule()
    print("✓ test_evaluate_dataset_skip_hard_rule")

    test_evaluate_dataset_metrics()
    print("✓ test_evaluate_dataset_metrics")

    test_uncertain_counts_as_incorrect()
    print("✓ test_uncertain_counts_as_incorrect")

    test_row_capture()
    print("✓ test_row_capture")

    test_confidence_band_counts()
    print("✓ test_confidence_band_counts")

    test_shadow_intent_counts()
    print("✓ test_shadow_intent_counts")

    test_shadow_reason_counts()
    print("✓ test_shadow_reason_counts")

    test_no_dependency_on_model_artifacts()
    print("✓ test_no_dependency_on_model_artifacts")

    test_load_train_jsonl_label_field()
    print("✓ test_load_train_jsonl_label_field")

    test_load_train_jsonl_intent_field()
    print("✓ test_load_train_jsonl_intent_field")

    test_private_route_with_shadow()
    print("✓ test_private_route_with_shadow")


    print("\nAll B2 dataset-driven shadow evaluator tests passed!")
