"""Test B2 Shadow Evaluator with deterministic in-memory fixtures."""

from collections import defaultdict, deque

from evaluation.shadow_evaluator import ShadowEvaluator, ShadowEvalReport
from router.intent_router import IntentRouter


class FakeRouter:
    """Fake router with controllable shadow stats."""
    
    def __init__(self):
        self._shadow_stats = {
            "model_checks": 0,
            "high_conf_predictions": 0,
            "fallback_activations": 0,
            "prediction_errors": 0,
            "shadow_intent_distribution": defaultdict(int),
            "shadow_reason_distribution": defaultdict(int),
            "shadow_confidence_distribution": deque(maxlen=10000),
            "public_disagreements": 0,
        }
    
    def get_shadow_stats(self):
        return {
            "model_checks": self._shadow_stats["model_checks"],
            "high_conf_predictions": self._shadow_stats["high_conf_predictions"],
            "fallback_activations": self._shadow_stats["fallback_activations"],
            "prediction_errors": self._shadow_stats["prediction_errors"],
            "shadow_intent_distribution": dict(self._shadow_stats["shadow_intent_distribution"]),
            "shadow_reason_distribution": dict(self._shadow_stats["shadow_reason_distribution"]),
            "shadow_confidence_distribution": list(self._shadow_stats["shadow_confidence_distribution"]),
            "public_disagreements": self._shadow_stats["public_disagreements"],
        }
    
    def reset_shadow_stats(self):
        self._shadow_stats = {
            "model_checks": 0,
            "high_conf_predictions": 0,
            "fallback_activations": 0,
            "prediction_errors": 0,
            "shadow_intent_distribution": defaultdict(int),
            "shadow_reason_distribution": defaultdict(int),
            "shadow_confidence_distribution": deque(maxlen=10000),
            "public_disagreements": 0,
        }


def test_metric_calculations_empty_stats():
    """Test metric calculations with empty shadow stats."""
    router = FakeRouter()
    evaluator = ShadowEvaluator(router)
    
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.total_queries == 0
    assert report.overall_accuracy == 0.0
    assert report.uncertain_rate == 0.0
    assert report.fallback_rate == 0.0
    assert report.public_disagreement_rate == 0.0
    assert report.confidence_band_counts == {"<0.60": 0, "0.60-0.79": 0, ">=0.80": 0}
    for intent in ["cv", "eco", "general", "uncertain"]:
        assert report.per_intent_accuracy[intent] == 0.0


def test_metric_calculations_with_data():
    """Test metric calculations with sample shadow stats."""
    router = FakeRouter()
    
    # Set up sample stats
    router._shadow_stats["model_checks"] = 10
    router._shadow_stats["high_conf_predictions"] = 6
    router._shadow_stats["fallback_activations"] = 2
    router._shadow_stats["public_disagreements"] = 4
    router._shadow_stats["shadow_intent_distribution"]["cv"] = 3
    router._shadow_stats["shadow_intent_distribution"]["eco"] = 2
    router._shadow_stats["shadow_intent_distribution"]["general"] = 3
    router._shadow_stats["shadow_intent_distribution"]["uncertain"] = 2
    router._shadow_stats["shadow_confidence_distribution"] = deque([0.5, 0.7, 0.85, 0.9, 0.55, 0.75, 0.82, 0.4, 0.65, 0.88], maxlen=10000)
    
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.total_queries == 10
    assert report.overall_accuracy == 0.6  # 6/10 high conf
    assert report.uncertain_rate == 0.2  # 2/10 uncertain
    assert report.fallback_rate == 0.2  # 2/10 fallback
    assert report.public_disagreement_rate == 0.4  # 4/10 disagreement
    
    # Per-intent accuracy
    assert report.per_intent_accuracy["cv"] == 0.3  # 3/10
    assert report.per_intent_accuracy["eco"] == 0.2  # 2/10
    assert report.per_intent_accuracy["general"] == 0.3  # 3/10
    assert report.per_intent_accuracy["uncertain"] == 0.2  # 2/10
    
    # Confidence band counts
    assert report.confidence_band_counts["<0.60"] == 3  # 0.5, 0.55, 0.4
    assert report.confidence_band_counts["0.60-0.79"] == 3  # 0.7, 0.75, 0.65
    assert report.confidence_band_counts[">=0.80"] == 4  # 0.85, 0.9, 0.82, 0.88


def test_confidence_band_counts():
    """Test confidence band counting logic."""
    router = FakeRouter()
    
    # Test low confidence band
    router._shadow_stats["model_checks"] = 5
    router._shadow_stats["shadow_confidence_distribution"] = deque([0.1, 0.3, 0.5, 0.55, 0.59], maxlen=10000)
    
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.confidence_band_counts["<0.60"] == 5
    assert report.confidence_band_counts["0.60-0.79"] == 0
    assert report.confidence_band_counts[">=0.80"] == 0
    
    # Test mid confidence band
    router._shadow_stats["shadow_confidence_distribution"] = deque([0.6, 0.7, 0.75, 0.79], maxlen=10000)
    router._shadow_stats["model_checks"] = 4
    
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.confidence_band_counts["<0.60"] == 0
    assert report.confidence_band_counts["0.60-0.79"] == 4
    assert report.confidence_band_counts[">=0.80"] == 0
    
    # Test high confidence band
    router._shadow_stats["shadow_confidence_distribution"] = deque([0.8, 0.85, 0.9, 0.95, 1.0], maxlen=10000)
    router._shadow_stats["model_checks"] = 5
    
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.confidence_band_counts["<0.60"] == 0
    assert report.confidence_band_counts["0.60-0.79"] == 0
    assert report.confidence_band_counts[">=0.80"] == 5


def test_uncertain_rate():
    """Test uncertain rate calculation."""
    router = FakeRouter()
    
    # 3 uncertain out of 10 total
    router._shadow_stats["model_checks"] = 10
    router._shadow_stats["shadow_intent_distribution"]["uncertain"] = 3
    router._shadow_stats["shadow_intent_distribution"]["cv"] = 4
    router._shadow_stats["shadow_intent_distribution"]["eco"] = 3
    
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.uncertain_rate == 0.3


def test_fallback_rate():
    """Test fallback rate calculation."""
    router = FakeRouter()
    
    # 2 fallbacks out of 10 total
    router._shadow_stats["model_checks"] = 10
    router._shadow_stats["fallback_activations"] = 2
    
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.fallback_rate == 0.2


def test_disagreement_rate():
    """Test public disagreement rate calculation."""
    router = FakeRouter()
    
    # 4 disagreements out of 10 total
    router._shadow_stats["model_checks"] = 10
    router._shadow_stats["public_disagreements"] = 4
    
    evaluator = ShadowEvaluator(router)
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.public_disagreement_rate == 0.4


def test_no_dependency_on_model_artifacts():
    """Test that evaluator works without model artifacts."""
    router = FakeRouter()
    evaluator = ShadowEvaluator(router)
    
    # Should work with just shadow stats, no model needed
    report = evaluator.evaluate_from_shadow_stats()
    
    assert report.total_queries == 0
    assert isinstance(report, ShadowEvalReport)


def test_labeled_data_evaluation():
    """Test evaluation from labeled queries."""
    from test_shadow_hybrid_router import FakeModel
    
    router = IntentRouter(model=FakeModel(prediction="cv", confidence=0.85))
    evaluator = ShadowEvaluator(router)
    
    queries = ["Query 1", "Query 2", "Query 3"]
    expected_intents = ["cv", "cv", "cv"]
    
    report = evaluator.evaluate_from_labeled_data(queries, expected_intents)
    
    assert report.total_queries == 3
    assert report.overall_accuracy > 0.0
    assert isinstance(report, ShadowEvalReport)


def test_labeled_data_length_mismatch():
    """Test that labeled data evaluation raises on length mismatch."""
    router = FakeRouter()
    evaluator = ShadowEvaluator(router)
    
    queries = ["Query 1", "Query 2"]
    expected_intents = ["cv"]
    
    try:
        evaluator.evaluate_from_labeled_data(queries, expected_intents)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "same length" in str(e)


if __name__ == "__main__":
    # Run tests
    test_metric_calculations_empty_stats()
    print("✓ test_metric_calculations_empty_stats")
    
    test_metric_calculations_with_data()
    print("✓ test_metric_calculations_with_data")
    
    test_confidence_band_counts()
    print("✓ test_confidence_band_counts")
    
    test_uncertain_rate()
    print("✓ test_uncertain_rate")
    
    test_fallback_rate()
    print("✓ test_fallback_rate")
    
    test_disagreement_rate()
    print("✓ test_disagreement_rate")
    
    test_no_dependency_on_model_artifacts()
    print("✓ test_no_dependency_on_model_artifacts")
    
    test_labeled_data_evaluation()
    print("✓ test_labeled_data_evaluation")
    
    test_labeled_data_length_mismatch()
    print("✓ test_labeled_data_length_mismatch")
    
    print("\nAll B2 shadow evaluator tests passed!")
