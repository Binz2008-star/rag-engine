from __future__ import annotations

import json
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline as SkPipeline

from app.config import ACTIVE_MODEL_PATH, ROUTER_CONFIDENCE_THRESHOLD
from app.models import Route
from router.features import extract_hints


class IntentRouter:
    def __init__(self, model: SkPipeline | None = None, threshold: float = ROUTER_CONFIDENCE_THRESHOLD):
        self.model = model
        self.threshold = threshold

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
        return cls.from_path(
            Path(meta["path"]),
            threshold=meta.get("threshold", ROUTER_CONFIDENCE_THRESHOLD),
        )

    def route(self, query: str) -> Route:
        eco_hint, cv_hint = extract_hints(query)

        if eco_hint and not cv_hint:
            return Route(intent="eco", confidence=1.0, intent_method="rule")

        if cv_hint and not eco_hint:
            return Route(intent="cv", confidence=1.0, intent_method="rule")

        return Route(intent="general", confidence=0.5, intent_method="rule")
