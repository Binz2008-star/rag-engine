"""Shadow evaluator for measuring shadow router quality.

This module evaluates shadow decision quality without affecting production behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from router.intent_router import IntentRouter
from router.features import extract_hints


@dataclass
class ShadowEvalRow:
    """Single row in shadow evaluation."""
    query: str
    expected_intent: str
    shadow_intent: str
    shadow_confidence: float
    shadow_reason: str
    public_intent: str
    public_disagreement: bool
    suite: str | None = None
    skipped_hard_rule: bool = False


@dataclass
class ShadowEvalReport:
    """Shadow evaluation report."""
    total_rows: int
    evaluated_rows: int
    skipped_hard_rule_rows: int
    overall_accuracy: float
    per_intent_accuracy: dict[str, float]
    uncertain_rate: float
    fallback_rate: float
    public_disagreement_rate: float
    confidence_band_counts: dict[str, int]
    shadow_intent_counts: dict[str, int]
    shadow_reason_counts: dict[str, int]
    rows: list[dict[str, Any]]


class ShadowEvaluator:
    """Evaluate shadow router quality from datasets."""

    def __init__(self, router: IntentRouter):
        self.router = router

    def load_train_jsonl(self, path: Path) -> list[dict[str, str]]:
        """Load training data from JSONL file.

        Args:
            path: Path to train.jsonl file

        Returns:
            List of dicts with 'query' and 'intent' keys
        """
        rows = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    rows.append({
                        "query": row["query"],
                        "expected_intent": row["intent"],
                    })
        return rows

    def load_eval_queries_json(self, path: Path) -> list[dict[str, Any]]:
        """Load evaluation queries from JSON file.

        Args:
            path: Path to eval_queries.json file

        Returns:
            List of dicts with 'query', 'expected_intent', and 'suite' keys
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        rows = []
        for item in data:
            rows.append({
                "query": item.get("query", item.get("question", "")),
                "expected_intent": item.get("expected_intent", "general"),
                "suite": item.get("suite"),
            })
        return rows

    def is_hard_rule(self, query: str) -> bool:
        """Check if query matches hard-rule patterns.

        Args:
            query: Query string

        Returns:
            True if query matches hard-rule pattern
        """
        eco_hint, cv_hint = extract_hints(query)
        q = query.lower()

        if "roben" in q or "roben's" in q:
            return True
        if eco_hint and not cv_hint:
            return True
        if cv_hint and not eco_hint:
            return True

        return False

    def evaluate_dataset(
        self,
        rows: list[dict[str, Any]],
    ) -> ShadowEvalReport:
        """Evaluate shadow router on dataset row-by-row.

        Args:
            rows: List of dicts with 'query', 'expected_intent', and optionally 'suite'

        Returns:
            ShadowEvalReport with detailed metrics
        """
        self.router.reset_shadow_stats()

        eval_rows = []
        total_rows = len(rows)
        skipped_hard_rule_rows = 0
        evaluated_rows = 0

        correct = 0
        uncertain_count = 0
        fallback_count = 0
        disagreement_count = 0

        intent_counts = {"cv": 0, "eco": 0, "general": 0, "uncertain": 0}
        reason_counts = {}
        confidence_band_counts = {"<0.60": 0, "0.60-0.79": 0, ">=0.80": 0}

        for row in rows:
            query = row["query"]
            expected_intent = row["expected_intent"]
            suite = row.get("suite")

            # Check if hard-rule
            if self.is_hard_rule(query):
                skipped_hard_rule_rows += 1
                eval_rows.append({
                    "query": query,
                    "expected_intent": expected_intent,
                    "shadow_intent": None,
                    "shadow_confidence": 0.0,
                    "shadow_reason": "hard_rule_bypass",
                    "public_intent": expected_intent,
                    "public_disagreement": False,
                    "suite": suite,
                    "skipped_hard_rule": True,
                })
                continue

            evaluated_rows += 1

            # Run query through router with shadow decision
            public_route, shadow_decision = self.router.route_with_shadow(query)

            # Extract shadow decision details
            if shadow_decision:
                shadow_intent = shadow_decision.intent
                shadow_confidence = shadow_decision.confidence
                shadow_reason = shadow_decision.reason
            else:
                shadow_intent = "general"
                shadow_confidence = 0.0
                shadow_reason = "no_shadow"

            # Calculate disagreement
            public_intent = public_route.intent
            public_disagreement = shadow_intent != public_intent

            # Track metrics
            if shadow_intent == expected_intent and shadow_intent != "uncertain":
                correct += 1
            if shadow_intent == "uncertain":
                uncertain_count += 1
            if shadow_reason == "low_confidence":
                fallback_count += 1
            if public_disagreement:
                disagreement_count += 1

            # Track intent counts
            intent_counts[shadow_intent] = intent_counts.get(shadow_intent, 0) + 1

            # Track reason counts
            reason_counts[shadow_reason] = reason_counts.get(shadow_reason, 0) + 1

            # Track confidence bands
            if shadow_confidence < 0.60:
                confidence_band_counts["<0.60"] += 1
            elif shadow_confidence < 0.80:
                confidence_band_counts["0.60-0.79"] += 1
            else:
                confidence_band_counts[">=0.80"] += 1

            eval_rows.append({
                "query": query,
                "expected_intent": expected_intent,
                "shadow_intent": shadow_intent,
                "shadow_confidence": shadow_confidence,
                "shadow_reason": shadow_reason,
                "public_intent": public_intent,
                "public_disagreement": public_disagreement,
                "suite": suite,
                "skipped_hard_rule": False,
            })

        # Calculate metrics
        overall_accuracy = correct / evaluated_rows if evaluated_rows > 0 else 0.0
        uncertain_rate = uncertain_count / evaluated_rows if evaluated_rows > 0 else 0.0
        fallback_rate = fallback_count / evaluated_rows if evaluated_rows > 0 else 0.0
        disagreement_rate = disagreement_count / evaluated_rows if evaluated_rows > 0 else 0.0

        # Per-intent accuracy
        per_intent_accuracy = {}
        for intent in ["cv", "eco", "general"]:
            intent_total = sum(1 for r in eval_rows if not r["skipped_hard_rule"] and r["expected_intent"] == intent)
            intent_correct = sum(1 for r in eval_rows if not r["skipped_hard_rule"] and r["expected_intent"] == intent and r["shadow_intent"] == intent and r["shadow_intent"] != "uncertain")
            per_intent_accuracy[intent] = intent_correct / intent_total if intent_total > 0 else 0.0

        return ShadowEvalReport(
            total_rows=total_rows,
            evaluated_rows=evaluated_rows,
            skipped_hard_rule_rows=skipped_hard_rule_rows,
            overall_accuracy=overall_accuracy,
            per_intent_accuracy=per_intent_accuracy,
            uncertain_rate=uncertain_rate,
            fallback_rate=fallback_rate,
            public_disagreement_rate=disagreement_rate,
            confidence_band_counts=confidence_band_counts,
            shadow_intent_counts=intent_counts,
            shadow_reason_counts=reason_counts,
            rows=eval_rows,
        )
