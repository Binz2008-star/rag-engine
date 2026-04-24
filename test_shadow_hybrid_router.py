"""Test B1 Shadow Hybrid Router with fake model stubs."""

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


def test_hard_rule_cv_bypass():
    """Test that CV hard-rule bypasses shadow classification."""
    fake_model = FakeModel(prediction="eco", confidence=0.9)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is roben's role?")
    
    # Public API
    assert result.intent == "cv"
    assert result.confidence == 1.0
    assert result.intent_method == "rule"
    
    # Shadow stats - model should not have been called
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["shadow_intent_distribution"] == {}
    assert stats["shadow_reason_distribution"] == {}


def test_hard_rule_eco_bypass():
    """Test that ECO hard-rule bypasses shadow classification."""
    fake_model = FakeModel(prediction="cv", confidence=0.9)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What environmental services does ECO provide?")
    
    # Public API
    assert result.intent == "eco"
    assert result.confidence == 1.0
    assert result.intent_method == "rule"
    
    # Shadow stats - model should not have been called
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["shadow_intent_distribution"] == {}
    assert stats["shadow_reason_distribution"] == {}


def test_conflicting_hints_uncertain():
    """Test conflicting hints → uncertain / conflicting_hints."""
    fake_model = FakeModel(prediction="cv", confidence=0.9)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    # Query with both eco and cv hints
    result = router.route("ECO CV services")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0  # Bypassed by conflicting hints
    assert stats["shadow_intent_distribution"]["uncertain"] == 1
    assert stats["shadow_reason_distribution"]["conflicting_hints"] == 1
    assert stats["public_disagreements"] == 1  # uncertain != general


def test_model_unavailable_general():
    """Test no model loaded → general / model_unavailable."""
    router = IntentRouter(model=None)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["shadow_intent_distribution"]["general"] == 1
    assert stats["shadow_reason_distribution"]["model_unavailable"] == 1
    assert stats["public_disagreements"] == 0  # general == general


def test_low_confidence_general():
    """Test confidence < 0.60 → general / low_confidence."""
    fake_model = FakeModel(prediction="cv", confidence=0.5)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["general"] == 1
    assert stats["shadow_reason_distribution"]["low_confidence"] == 1
    assert stats["fallback_activations"] == 1  # Legacy counter
    assert stats["public_disagreements"] == 0  # general == general


def test_mid_confidence_uncertain():
    """Test 0.60 ≤ confidence < 0.80 → uncertain / mid_confidence_uncertain."""
    fake_model = FakeModel(prediction="cv", confidence=0.7)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["uncertain"] == 1
    assert stats["shadow_reason_distribution"]["mid_confidence_uncertain"] == 1
    assert stats["public_disagreements"] == 1  # uncertain != general


def test_high_confidence_cv():
    """Test confidence ≥ 0.80 → cv / high_confidence_prediction."""
    fake_model = FakeModel(prediction="cv", confidence=0.85)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["cv"] == 1
    assert stats["shadow_reason_distribution"]["high_confidence_prediction"] == 1
    assert stats["high_conf_predictions"] == 1  # Legacy counter
    assert stats["public_disagreements"] == 1  # cv != general


def test_high_confidence_eco():
    """Test confidence ≥ 0.80 → eco / high_confidence_prediction."""
    fake_model = FakeModel(prediction="eco", confidence=0.9)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["eco"] == 1
    assert stats["shadow_reason_distribution"]["high_confidence_prediction"] == 1
    assert stats["public_disagreements"] == 1  # eco != general


def test_high_confidence_general():
    """Test confidence ≥ 0.80 → general / high_confidence_prediction."""
    fake_model = FakeModel(prediction="general", confidence=0.85)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["general"] == 1
    assert stats["shadow_reason_distribution"]["high_confidence_prediction"] == 1
    assert stats["public_disagreements"] == 0  # general == general


def test_model_error_handling():
    """Test model exception → general / model_error."""
    class BrokenModel:
        def predict(self, X):
            raise ValueError("Model is broken")
    
    router = IntentRouter(model=BrokenModel())
    router.reset_shadow_stats()
    
    result = router.route("What is the GDP of Japan?")
    
    # Public API unchanged
    assert result.intent == "general"
    assert result.confidence == 0.5
    assert result.intent_method == "rule"
    
    # Shadow stats
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 1
    assert stats["shadow_intent_distribution"]["general"] == 1
    assert stats["shadow_reason_distribution"]["model_error"] == 1
    assert stats["public_disagreements"] == 0  # general == general


def test_disagreement_counting():
    """Test disagreement counting (shadow_intent != public_intent)."""
    fake_model = FakeModel(prediction="cv", confidence=0.85)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    # Run 3 queries that will disagree
    router.route("Query 1")
    router.route("Query 2")
    router.route("Query 3")
    
    stats = router.get_shadow_stats()
    assert stats["public_disagreements"] == 3
    
    # Run 1 query that agrees (general prediction)
    fake_model.prediction = "general"
    router.route("Query 4")
    
    stats = router.get_shadow_stats()
    assert stats["public_disagreements"] == 3  # Still 3 (general == general)


def test_stats_reset():
    """Test shadow stats reset."""
    fake_model = FakeModel(prediction="cv", confidence=0.85)
    router = IntentRouter(model=fake_model)
    
    router.route("Query 1")
    router.route("Query 2")
    
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 2
    assert stats["public_disagreements"] == 2
    
    router.reset_shadow_stats()
    
    stats = router.get_shadow_stats()
    assert stats["model_checks"] == 0
    assert stats["public_disagreements"] == 0
    assert stats["shadow_intent_distribution"] == {}
    assert stats["shadow_reason_distribution"] == {}


def test_bounded_confidence_distribution():
    """Test confidence distribution uses deque with maxlen=10000."""
    fake_model = FakeModel(prediction="cv", confidence=0.85)
    router = IntentRouter(model=fake_model)
    router.reset_shadow_stats()
    
    # Run many queries
    for i in range(100):
        router.route(f"Query {i}")
    
    stats = router.get_shadow_stats()
    assert len(stats["shadow_confidence_distribution"]) == 100
    assert all(c == 0.85 for c in stats["shadow_confidence_distribution"])
    
    # Verify it's a deque (bounded)
    from collections import deque
    assert isinstance(router._shadow_stats["shadow_confidence_distribution"], deque)
    assert router._shadow_stats["shadow_confidence_distribution"].maxlen == 10000


def test_public_route_unchanged():
    """Test public Route contract remains unchanged."""
    fake_model = FakeModel(prediction="cv", confidence=0.95)
    router = IntentRouter(model=fake_model)
    
    # All non-rule queries return general/0.5/rule
    queries = [
        "What is the GDP of Japan?",
        "Tell me about quantum physics",
        "How do companies measure efficiency?",
    ]
    
    for query in queries:
        result = router.route(query)
        assert result.intent == "general"
        assert result.confidence == 0.5
        assert result.intent_method == "rule"
    
    # Hard-rule queries still work
    result = router.route("What is roben's role?")
    assert result.intent == "cv"
    assert result.confidence == 1.0
    assert result.intent_method == "rule"


if __name__ == "__main__":
    # Run tests
    test_hard_rule_cv_bypass()
    print("✓ test_hard_rule_cv_bypass")
    
    test_hard_rule_eco_bypass()
    print("✓ test_hard_rule_eco_bypass")
    
    test_conflicting_hints_uncertain()
    print("✓ test_conflicting_hints_uncertain")
    
    test_model_unavailable_general()
    print("✓ test_model_unavailable_general")
    
    test_low_confidence_general()
    print("✓ test_low_confidence_general")
    
    test_mid_confidence_uncertain()
    print("✓ test_mid_confidence_uncertain")
    
    test_high_confidence_cv()
    print("✓ test_high_confidence_cv")
    
    test_high_confidence_eco()
    print("✓ test_high_confidence_eco")
    
    test_high_confidence_general()
    print("✓ test_high_confidence_general")
    
    test_model_error_handling()
    print("✓ test_model_error_handling")
    
    test_disagreement_counting()
    print("✓ test_disagreement_counting")
    
    test_stats_reset()
    print("✓ test_stats_reset")
    
    test_bounded_confidence_distribution()
    print("✓ test_bounded_confidence_distribution")
    
    test_public_route_unchanged()
    print("✓ test_public_route_unchanged")
    
    print("\nAll B1 shadow hybrid router tests passed!")
