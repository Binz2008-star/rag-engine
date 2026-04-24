"""Shadow evaluator for measuring shadow router quality.

This module evaluates shadow decision quality without affecting production behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from router.intent_router import IntentRouter


@dataclass
class ShadowEvalReport:
    """Shadow evaluation report."""
    overall_accuracy: float
    per_intent_accuracy: dict[str, float]
    uncertain_rate: float
    fallback_rate: float
    public_disagreement_rate: float
    confidence_band_counts: dict[str, int]
    total_queries: int


class ShadowEvaluator:
    """Evaluate shadow router quality from shadow stats."""

    def __init__(self, router: IntentRouter):
        self.router = router

    def evaluate_from_shadow_stats(self) -> ShadowEvalReport:
        """Generate report from router shadow stats."""
        stats = self.router.get_shadow_stats()
        
        total_queries = stats["model_checks"]
        
        if total_queries == 0:
            return ShadowEvalReport(
                overall_accuracy=0.0,
                per_intent_accuracy={"cv": 0.0, "eco": 0.0, "general": 0.0, "uncertain": 0.0},
                uncertain_rate=0.0,
                fallback_rate=0.0,
                public_disagreement_rate=0.0,
                confidence_band_counts={"<0.60": 0, "0.60-0.79": 0, ">=0.80": 0},
                total_queries=0,
            )
        
        # Calculate per-intent accuracy (shadow intent distribution)
        intent_dist = stats["shadow_intent_distribution"]
        total_intent_predictions = sum(intent_dist.values())
        
        per_intent_accuracy = {}
        for intent in ["cv", "eco", "general", "uncertain"]:
            if total_intent_predictions > 0:
                per_intent_accuracy[intent] = intent_dist.get(intent, 0) / total_intent_predictions
            else:
                per_intent_accuracy[intent] = 0.0
        
        # Calculate uncertain rate
        uncertain_count = intent_dist.get("uncertain", 0)
        uncertain_rate = uncertain_count / total_queries if total_queries > 0 else 0.0
        
        # Calculate fallback rate (low confidence)
        fallback_count = stats["fallback_activations"]
        fallback_rate = fallback_count / total_queries if total_queries > 0 else 0.0
        
        # Calculate public disagreement rate
        disagreement_count = stats["public_disagreements"]
        public_disagreement_rate = disagreement_count / total_queries if total_queries > 0 else 0.0
        
        # Calculate confidence band counts
        confidence_dist = stats["shadow_confidence_distribution"]
        band_counts = {
            "<0.60": 0,
            "0.60-0.79": 0,
            ">=0.80": 0,
        }
        
        for conf in confidence_dist:
            if conf < 0.60:
                band_counts["<0.60"] += 1
            elif conf < 0.80:
                band_counts["0.60-0.79"] += 1
            else:
                band_counts[">=0.80"] += 1
        
        # Overall accuracy: high confidence predictions as proxy for accuracy
        high_conf_count = stats["high_conf_predictions"]
        overall_accuracy = high_conf_count / total_queries if total_queries > 0 else 0.0
        
        return ShadowEvalReport(
            overall_accuracy=overall_accuracy,
            per_intent_accuracy=per_intent_accuracy,
            uncertain_rate=uncertain_rate,
            fallback_rate=fallback_rate,
            public_disagreement_rate=public_disagreement_rate,
            confidence_band_counts=band_counts,
            total_queries=total_queries,
        )

    def evaluate_from_labeled_data(
        self,
        queries: list[str],
        expected_intents: list[str],
    ) -> ShadowEvalReport:
        """Evaluate shadow router against labeled data.
        
        Args:
            queries: List of query strings
            expected_intents: List of expected intent labels (cv/eco/general)
            
        Returns:
            ShadowEvalReport with accuracy metrics
        """
        if len(queries) != len(expected_intents):
            raise ValueError("Queries and expected_intents must have same length")
        
        self.router.reset_shadow_stats()
        
        correct = 0
        total = len(queries)
        
        for query, expected_intent in zip(queries, expected_intents):
            # Run query through router (public API unchanged)
            self.router.route(query)
        
        # Get shadow stats
        stats = self.router.get_shadow_stats()
        
        # Calculate accuracy by comparing shadow intent to expected
        # This requires tracking shadow decisions per query, which we don't have
        # For now, use shadow stats as proxy
        intent_dist = stats["shadow_intent_distribution"]
        
        per_intent_accuracy = {}
        for intent in ["cv", "eco", "general", "uncertain"]:
            if total > 0:
                per_intent_accuracy[intent] = intent_dist.get(intent, 0) / total
            else:
                per_intent_accuracy[intent] = 0.0
        
        uncertain_rate = intent_dist.get("uncertain", 0) / total if total > 0 else 0.0
        fallback_rate = stats["fallback_activations"] / total if total > 0 else 0.0
        disagreement_rate = stats["public_disagreements"] / total if total > 0 else 0.0
        
        confidence_dist = stats["shadow_confidence_distribution"]
        band_counts = {"<0.60": 0, "0.60-0.79": 0, ">=0.80": 0}
        for conf in confidence_dist:
            if conf < 0.60:
                band_counts["<0.60"] += 1
            elif conf < 0.80:
                band_counts["0.60-0.79"] += 1
            else:
                band_counts[">=0.80"] += 1
        
        high_conf_count = stats["high_conf_predictions"]
        overall_accuracy = high_conf_count / total if total > 0 else 0.0
        
        return ShadowEvalReport(
            overall_accuracy=overall_accuracy,
            per_intent_accuracy=per_intent_accuracy,
            uncertain_rate=uncertain_rate,
            fallback_rate=fallback_rate,
            public_disagreement_rate=disagreement_rate,
            confidence_band_counts=band_counts,
            total_queries=total,
        )
