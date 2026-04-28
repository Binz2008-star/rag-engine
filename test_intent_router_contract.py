"""Test IntentRouter contract stabilization with fake model stubs."""

from typing import Any
from unittest.mock import MagicMock

from router.intent_router import IntentRouter


class FakeModel:
    """Fake sklearn Pipeline stub for testing."""

    def __init__(self, prediction: str = "general", confidence: float = 0.7):
        self.prediction = prediction
        self.confidence = confidence

    def predict(self, X):
        return [self.prediction] * len(X)

    def predict_proba(self, X):
        import numpy as np
        # Return fake probability distribution
        n_classes = 3  # cv, eco, general
        probs = np.zeros((len(X), n_classes))

        # Distribute remaining probability evenly among other classes
        remaining_prob = (1.0 - self.confidence) / (n_classes - 1)

        # Set confidence for predicted class
        if self.prediction == "cv":
            probs[:, 0] = self.confidence
            probs[:, 1] = remaining_prob
            probs[:, 2] = remaining_prob
        elif self.prediction == "eco":
            probs[:, 0] = remaining_prob
            probs[:, 1] = self.confidence
            probs[:, 2] = remaining_prob
        else:  # general
            probs[:, 0] = remaining_prob
            probs[:, 1] = remaining_prob
            probs[:, 2] = self.confidence

        return probs


def test_hard_rule_bypasses_model():
    """Test that CV/ECO hard-rules bypass model execution entirely."""
    # Create router with fake model
    fake_model = FakeModel(prediction="eco", confidence=0.9)
    router = IntentRouter(model=fake_model)

    # Reset shadow stats
    router.reset_shadow_stats()

    # Test CV hard-rule (roben keyword)
    result = router.route("What is roben's role?")
    assert result.intent == "cv"
    assert result.confidence == 1.0
    assert result.intent_method == "rule"

    # Model should not have been called (shadow stats should be 0)
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 0
    assert stats["prediction_errors"] == 0

    # Test ECO hard-rule
    result = router.route("What environmental services does ECO provide?")
    assert result.intent == "eco"
    assert result.confidence == 1.0
    assert result.intent_method == "rule"

    # Model should still not have been called
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 0
    assert stats["prediction_errors"] == 0


def test_non_rule_returns_general():
    """Test that non-rule queries always return general/0.5/rule publicly."""
    # Create router with fake model that predicts eco with high confidence
    fake_model = FakeModel(prediction="eco", confidence=0.95)
    router = IntentRouter(model=fake_model)

    router.reset_shadow_stats()

    # Query with no hard-rule hints
    result = router.route("What is the GDP of Japan?")

    # Public API should always return general/0.5/rule
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"

    # But shadow stats should show the model was called
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["high_conf_predictions"] == 1
    assert stats["fallback_activations"] == 0
    assert stats["prediction_errors"] == 0
    assert stats["shadow_intent_distribution"]["eco"] == 1
    assert len(stats["shadow_confidence_distribution"]) == 1
    assert stats["shadow_confidence_distribution"][0] == 0.95


def test_no_model_leak_in_public_api():
    """Test that 'model' or 'model_fallback' never leak into public intent_method."""
    # Create router with fake model
    fake_model = FakeModel(prediction="cv", confidence=0.3)
    router = IntentRouter(model=fake_model)

    router.reset_shadow_stats()

    # Run various queries
    queries = [
        "What is the GDP of Japan?",
        "Tell me about quantum physics",
        "How do companies measure efficiency?",
    ]

    for query in queries:
        result = router.route(query)
        # Public intent_method should always be "rule"
        assert result.intent_method == "rule", f"Query: {query}, got: {result.intent_method}"
        # Should never be "model" or "model_fallback"
        assert result.intent_method not in ["model", "model_fallback"]


def test_shadow_stats_resettable():
    """Test that shadow stats are instance-local and resettable."""
    # Create router with fake model
    fake_model = FakeModel(prediction="general", confidence=0.8)
    router = IntentRouter(model=fake_model)

    # Run some queries
    router.route("Query 1")
    router.route("Query 2")
    router.route("Query 3")

    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 3
    assert stats["high_conf_predictions"] == 3

    # Reset stats
    router.reset_shadow_stats()

    # Stats should be cleared
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 0
    assert stats["prediction_errors"] == 0
    assert stats["shadow_intent_distribution"] == {}
    assert stats["shadow_confidence_distribution"] == []

    # Run more queries
    router.route("Query 4")
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["high_conf_predictions"] == 1


def test_shadow_stats_instance_local():
    """Test that shadow stats are instance-local (not shared between instances)."""
    # Create two router instances with the same fake model
    fake_model = FakeModel(prediction="eco", confidence=0.7)
    router1 = IntentRouter(model=fake_model)
    router2 = IntentRouter(model=fake_model)

    # Run queries on router1
    router1.route("Query 1")
    router1.route("Query 2")

    # Run queries on router2
    router2.route("Query 3")

    # Stats should be independent
    stats1 = router1.get_shadow_stats()
    stats2 = router2.get_shadow_stats()

    assert stats1["model_checks"] == 2
    assert stats2["model_checks"] == 1


def test_model_none_handling():
    """Test that router handles None model gracefully."""
    # Create router with no model
    router = IntentRouter(model=None)

    router.reset_shadow_stats()

    # Non-rule query should still work
    result = router.route("What is the GDP of Japan?")
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"

    # Shadow stats should remain 0 (no model to run)
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 0
    assert stats["prediction_errors"] == 0


def test_shadow_stats_distribution():
    """Test that shadow stats track intent distribution correctly."""
    # Create router with fake model that varies predictions
    router = IntentRouter(model=FakeModel(prediction="eco", confidence=0.8))

    router.reset_shadow_stats()

    # Run queries (all non-rule, so all run shadow classification)
    router.route("Query 1")
    router.route("Query 2")
    router.route("Query 3")

    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 3
    assert stats["high_conf_predictions"] == 3
    assert stats["shadow_intent_distribution"]["eco"] == 3
    assert len(stats["shadow_confidence_distribution"]) == 3
    assert all(c == 0.8 for c in stats["shadow_confidence_distribution"])


def test_low_confidence_shadow():
    """Test that low confidence predictions trigger fallback counter."""
    # Create router with fake model with low confidence
    fake_model = FakeModel(prediction="general", confidence=0.5)  # Below 0.6 threshold
    router = IntentRouter(model=fake_model)

    router.reset_shadow_stats()

    # Non-rule query
    result = router.route("What is the GDP of Japan?")

    # Public API should still return general/0.5/rule
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"

    # Shadow stats should show fallback activation
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 1
    assert stats["prediction_errors"] == 0


def test_model_error_handling():
    """Test that model errors are counted in prediction_errors."""
    # Create router with fake model that will raise an error
    class BrokenModel:
        def predict(self, X):
            raise ValueError("Model is broken")

    router = IntentRouter(model=BrokenModel())
    router.reset_shadow_stats()

    # Non-rule query
    result = router.route("What is the GDP of Japan?")

    # Public API should still return general/0.5/rule
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"

    # Shadow stats should show prediction error
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["prediction_errors"] == 1
    assert stats["high_conf_predictions"] == 0
    assert stats["fallback_activations"] == 0
    assert stats["shadow_reason_distribution"]["model_error"] == 1


if __name__ == "__main__":
    # Run tests
    test_hard_rule_bypasses_model()
    print("✓ test_hard_rule_bypasses_model")

    test_non_rule_returns_general()
    print("✓ test_non_rule_returns_general")

    test_no_model_leak_in_public_api()
    print("✓ test_no_model_leak_in_public_api")

    test_shadow_stats_resettable()
    print("✓ test_shadow_stats_resettable")

    test_shadow_stats_instance_local()
    print("✓ test_shadow_stats_instance_local")

    test_model_none_handling()
    print("✓ test_model_none_handling")

    test_shadow_stats_distribution()
    print("✓ test_shadow_stats_distribution")

    test_low_confidence_shadow()
    print("✓ test_low_confidence_shadow")

    test_model_error_handling()
    print("✓ test_model_error_handling")

    print("\nAll contract stabilization tests passed!")
