from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
from sklearn.pipeline import Pipeline as SkPipeline

from app.config import ACTIVE_MODEL_PATH, MODEL_DIR, ROUTER_CONFIDENCE_THRESHOLD
from app.models import Route
from router.features import extract_hints

logger = logging.getLogger(__name__)

FALLBACK_THRESHOLD = 0.6
MID_CONF_THRESHOLD = 0.8


@dataclass
class ShadowDecision:
    """Module-local shadow decision (internal-only, not exposed publicly)."""
    intent: str
    confidence: float
    reason: str


class IntentRouter:
    def __init__(self, model: SkPipeline | None = None, threshold: float = ROUTER_CONFIDENCE_THRESHOLD):
        self.model = model
        self.threshold = threshold
        # Shadow stats - instance-local, resettable
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

    @classmethod
    def from_path(
        cls,
        path: Path,
        threshold: float = ROUTER_CONFIDENCE_THRESHOLD,
    ) -> "IntentRouter":
        model = joblib.load(path)
        return cls(model=model, threshold=threshold)

    @classmethod
    def from_active_model(cls) -> "IntentRouter":
        if not ACTIVE_MODEL_PATH.exists():
            return cls(model=None)

        meta = json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
        model_path = Path(meta["path"])
        # Resolve relative to MODEL_DIR, not current working directory
        if not model_path.is_absolute():
            model_path = MODEL_DIR / model_path

        # Check if model file exists (may not be present in CI)
        if not model_path.exists():
            return cls(model=None)

        return cls.from_path(
            model_path,
            threshold=meta.get("threshold", ROUTER_CONFIDENCE_THRESHOLD),
        )

    def _run_shadow_classification(self, query: str, eco_hint: bool, cv_hint: bool) -> ShadowDecision:
        """Run shadow classification with decision priority logic (internal-only)."""
        # Priority 1: conflicting hints
        if eco_hint and cv_hint:
            decision = ShadowDecision(intent="uncertain", confidence=0.0, reason="conflicting_hints")
            self._track_shadow_decision(decision, public_intent="general")
            return decision

        # Priority 2: no model loaded
        if self.model is None:
            decision = ShadowDecision(intent="general", confidence=0.0, reason="model_unavailable")
            self._track_shadow_decision(decision, public_intent="general")
            return decision

        self._shadow_stats["model_checks"] += 1

        try:
            prediction = str(self.model.predict([query])[0])
            probabilities = self.model.predict_proba([query])[0]
            confidence = float(max(probabilities))

            # Priority 3: model exception (caught below)
            # Priority 4: low confidence
            if confidence < FALLBACK_THRESHOLD:
                decision = ShadowDecision(intent="general", confidence=confidence, reason="low_confidence")
                self._track_shadow_decision(decision, public_intent="general")
                return decision

            # Priority 5: mid confidence
            if confidence < MID_CONF_THRESHOLD:
                decision = ShadowDecision(intent="uncertain", confidence=confidence, reason="mid_confidence_uncertain")
                self._track_shadow_decision(decision, public_intent="general")
                return decision

            # Priority 6: high confidence
            decision = ShadowDecision(intent=prediction, confidence=confidence, reason="high_confidence_prediction")
            self._track_shadow_decision(decision, public_intent="general")
            return decision

        except Exception as exc:
            # Priority 3: model exception
            self._shadow_stats["prediction_errors"] += 1  # Backward compatibility
            decision = ShadowDecision(intent="general", confidence=0.0, reason="model_error")
            self._track_shadow_decision(decision, public_intent="general")
            logger.warning("Shadow ML model prediction failed: %s", exc)
            return decision

    def _track_shadow_decision(self, decision: ShadowDecision, public_intent: str) -> None:
        """Track shadow decision statistics (internal-only)."""
        self._shadow_stats["shadow_intent_distribution"][decision.intent] += 1
        self._shadow_stats["shadow_reason_distribution"][decision.reason] += 1

        if decision.confidence > 0:
            self._shadow_stats["shadow_confidence_distribution"].append(decision.confidence)

        # Track disagreement with public route
        if decision.intent != public_intent:
            self._shadow_stats["public_disagreements"] += 1

        # Track legacy counters for backward compatibility
        if decision.reason == "low_confidence":
            self._shadow_stats["fallback_activations"] += 1
        elif decision.reason == "high_confidence_prediction":
            self._shadow_stats["high_conf_predictions"] += 1

    def get_shadow_stats(self) -> dict[str, Any]:
        """Get shadow classification statistics (instance-local)."""
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

    def reset_shadow_stats(self) -> None:
        """Reset shadow classification statistics (instance-local)."""
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

    def route(self, query: str) -> Route:
        eco_hint, cv_hint = extract_hints(query)

        # Hard-rule routes bypass model execution entirely
        q = query.lower()
        if "roben" in q or "roben's" in q:
            return Route(intent="cv", confidence=1.0, intent_method="rule")

        if eco_hint and not cv_hint:
            return Route(intent="eco", confidence=1.0, intent_method="rule")

        if cv_hint and not eco_hint:
            return Route(intent="cv", confidence=1.0, intent_method="rule")

        # Run shadow classification (internal tracking only, not exposed publicly)
        self._run_shadow_classification(query, eco_hint=eco_hint, cv_hint=cv_hint)

        # Non-rule queries always return general/0.5/rule publicly
        return Route(intent="general", confidence=0.5, intent_method="rule")

    def _route_with_shadow(self, query: str) -> tuple[Route, ShadowDecision | None]:
        """Route query and return both public route and shadow decision.

        This method is for internal evaluation only and does not affect
        the public route contract.

        Args:
            query: Query string

        Returns:
            Tuple of (public Route, shadow ShadowDecision or None)
        """
        eco_hint, cv_hint = extract_hints(query)

        # Hard-rule routes bypass model execution entirely
        q = query.lower()
        if "roben" in q or "roben's" in q:
            route = Route(intent="cv", confidence=1.0, intent_method="rule")
            return route, None

        if eco_hint and not cv_hint:
            route = Route(intent="eco", confidence=1.0, intent_method="rule")
            return route, None

        if cv_hint and not eco_hint:
            route = Route(intent="cv", confidence=1.0, intent_method="rule")
            return route, None

        # Run shadow classification
        shadow_decision = self._run_shadow_classification(query, eco_hint=eco_hint, cv_hint=cv_hint)

        # Non-rule queries always return general/0.5/rule publicly
        route = Route(intent="general", confidence=0.5, intent_method="rule")
        return route, shadow_decision
