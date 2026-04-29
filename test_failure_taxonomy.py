"""Tests for failure taxonomy migration and normalization."""

from __future__ import annotations

import json

import pytest

from app.models import FailureType, normalize_legacy_failure_type, PipelineResult, RetrievalHit
from evaluation.metrics import compute_metrics


def test_normalize_legacy_failure_type_retrieval_miss():
    """Legacy retrieval_miss maps to retrieval_empty."""
    assert normalize_legacy_failure_type("retrieval_miss") == "retrieval_empty"


def test_normalize_legacy_failure_type_hallucination():
    """Legacy hallucination maps to grounding_reject."""
    assert normalize_legacy_failure_type("hallucination") == "grounding_reject"


def test_normalize_legacy_failure_type_none():
    """None returns None."""
    assert normalize_legacy_failure_type(None) is None


def test_normalize_legacy_failure_type_unknown():
    """Unknown labels pass through unchanged."""
    assert normalize_legacy_failure_type("unknown_label") == "unknown_label"


def test_normalize_legacy_failure_type_current_labels():
    """Current FailureType labels pass through unchanged."""
    for ft in FailureType:
        assert normalize_legacy_failure_type(ft.value) == ft.value


def test_metrics_rollup_retrieval_failures():
    """Metrics rollup includes retrieval_empty, retrieval_low_score, term_overlap_miss."""
    results = [
        {"passed": False, "failure_type": "retrieval_empty", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
        {"passed": False, "failure_type": "retrieval_low_score", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
        {"passed": False, "failure_type": "term_overlap_miss", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert metrics["retrieval_failure_rate"] == 1.0
    assert metrics["grounding_failure_rate"] == 0.0


def test_metrics_rollup_grounding_failures():
    """Metrics rollup includes grounding_reject, speculative_reject."""
    results = [
        {"passed": False, "failure_type": "grounding_reject", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
        {"passed": False, "failure_type": "speculative_reject", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert metrics["grounding_failure_rate"] == 1.0
    assert metrics["retrieval_failure_rate"] == 0.0


def test_metrics_rollup_safety_failures():
    """Metrics rollup includes sensitive_reject, injection_reject."""
    results = [
        {"passed": False, "failure_type": "sensitive_reject", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
        {"passed": False, "failure_type": "injection_reject", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert metrics["safety_failure_rate"] == 1.0
    assert metrics["retrieval_failure_rate"] == 0.0


def test_metrics_rollup_routing_failures():
    """Metrics rollup includes routing_miss."""
    results = [
        {"passed": False, "failure_type": "routing_miss", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert metrics["routing_failure_rate"] == 1.0


def test_metrics_rollup_translation_failures():
    """Metrics rollup includes translation_failure."""
    results = [
        {"passed": False, "failure_type": "translation_failure", "expected_refusal": False, "answer": "", "expected_intent": "general", "intent": "general", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert metrics["translation_failure_rate"] == 1.0


def test_metrics_no_legacy_labels():
    """Metrics does not reference retired labels hallucination or retrieval_miss."""
    results = [
        {"passed": True, "failure_type": None, "expected_refusal": False, "answer": "ok", "expected_intent": "eco", "intent": "eco", "latency_ms": 100},
    ]
    metrics = compute_metrics(results)
    assert "hallucination_rate" not in metrics
    assert "retrieval_miss_rate" not in metrics


def test_failure_type_enum_serialization():
    """FailureType enum serializes to plain string value."""
    result = PipelineResult(
        query_id="test",
        query="test query",
        normalized_query="test query",
        intent="general",
        confidence=1.0,
        intent_method="rule",
        retrieval=[],
        answer="Insufficient data.",
        grounded=True,
        failure_type=FailureType.RETRIEVAL_EMPTY,
    )
    # Simulate JSON serialization
    serialized = json.dumps({"failure_type": result.failure_type})
    assert '"failure_type": "retrieval_empty"' in serialized


def test_failure_type_none_serialization():
    """None failure_type serializes correctly."""
    result = PipelineResult(
        query_id="test",
        query="test query",
        normalized_query="test query",
        intent="general",
        confidence=1.0,
        intent_method="rule",
        retrieval=[],
        answer="ok",
        grounded=True,
        failure_type=None,
    )
    serialized = json.dumps({"failure_type": result.failure_type})
    assert '"failure_type": null' in serialized


def test_eval_rows_distinguish_failure_types():
    """Eval queries can distinguish between different failure types."""
    # This is a structural test - the actual eval_queries.json should have
    # different expected_failure_type values for different query types
    from pathlib import Path
    eval_queries = json.loads(Path("tests/eval_queries.json").read_text(encoding="utf-8"))
    
    failure_types = set()
    for q in eval_queries:
        if "expected_failure_type" in q:
            failure_types.add(q["expected_failure_type"])
    
    # Should have at least the types we set in the migration
    assert "retrieval_empty" in failure_types
    assert "routing_miss" in failure_types
    assert "sensitive_reject" in failure_types
    assert "translation_failure" in failure_types


def test_all_failure_types_covered():
    """All FailureType enum values are valid and distinct."""
    values = [ft.value for ft in FailureType]
    assert len(values) == len(set(values)), "FailureType values must be unique"
    
    # Verify all expected types are present
    expected = {
        "routing_miss",
        "retrieval_empty",
        "retrieval_low_score",
        "term_overlap_miss",
        "grounding_reject",
        "speculative_reject",
        "injection_reject",
        "sensitive_reject",
        "translation_failure",
    }
    assert set(values) == expected
