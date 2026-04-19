"""Deterministic document suggestions derived from alerts.

Closes the observe → detect → decide loop with an explicit "what to do
next" recommendation. No LLM, no search API, no scraping, no embeddings:
the suggestion policy is a primary signal from the alert itself plus a
small human-maintained fallback catalog keyed by topic.

The catalog lives in code on purpose — it is the operator's curated map
from topic to known-useful document names, auditable via diff review.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from analysis.alerts import generate_alerts
from analysis.drift_detector import _load_events_from_store, detect_drift

logger = logging.getLogger(__name__)

# Human-maintained fallback catalog. Only entries here are ever
# suggested when `top_missing_source` is unavailable. Keep small and
# reviewed; this is policy, not data.
_TOPIC_FALLBACKS: dict[str, tuple[str, ...]] = {
    "environmental_permits": (
        "municipal_regulations_2024.pdf",
        "fuel_station_permit_guidelines.pdf",
    ),
    "environmental_compliance": (
        "environmental_compliance_handbook.pdf",
    ),
    "wastewater": (
        "wastewater_compliance_guide.pdf",
    ),
    "grease_management": (
        "grease_trap_maintenance_manual.pdf",
    ),
    "waste_management": (
        "waste_management_policy.pdf",
    ),
    "municipality": (
        "municipal_regulations_2024.pdf",
    ),
    "audits": (
        "audit_procedures_reference.pdf",
    ),
    "tenders": (
        "tender_submission_template.pdf",
    ),
    "certificates": (
        "certification_requirements.pdf",
    ),
    "cv": (
        "cv_updated_template.pdf",
    ),
}

_ACTIONABLE_ACTION = "add_documents"


def suggest_documents(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate document-add recommendations for actionable alerts.

    Only alerts whose `action == "add_documents"` produce suggestions;
    medium-priority "investigate" alerts are skipped since the remedy
    is diagnosis, not ingestion.

    For each actionable alert:
        1. `top_missing_source` from evidence is the primary suggestion.
        2. Topic-keyed fallbacks are appended from the curated catalog.
        3. The merged list is deduplicated preserving order.
        4. `confidence` surfaces the drift_score that triggered the alert.
    """
    results: list[dict[str, Any]] = []

    for alert in alerts:
        if not isinstance(alert, dict) or alert.get("action") != _ACTIONABLE_ACTION:
            continue

        topic = alert.get("topic")
        evidence = alert.get("evidence") or {}
        if not isinstance(topic, str) or not topic:
            logger.warning("Skipping alert with missing/invalid topic: %r", alert)
            continue

        suggestions: list[str] = []

        primary = evidence.get("top_missing_source")
        if isinstance(primary, str) and primary:
            suggestions.append(primary)

        suggestions.extend(_TOPIC_FALLBACKS.get(topic, ()))

        deduped = list(dict.fromkeys(suggestions))

        try:
            confidence = round(float(evidence.get("drift_score", 0.0)), 2)
        except (TypeError, ValueError):
            confidence = 0.0

        source_hint = "top_missing_source" if primary else "topic_fallback"
        if not deduped:
            source_hint = "none"

        results.append({
            "topic": topic,
            "suggested_documents": deduped,
            "source_hint": source_hint,
            "confidence": confidence,
        })

    return results


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Suggest documents to add based on drift alerts.")
    parser.add_argument("--min-queries", type=int, default=5, help="Minimum queries per topic for drift detection.")
    parser.add_argument("--min-misses", type=int, default=3, help="Minimum misses per topic for drift detection.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON suggestions report.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        events = _load_events_from_store()
    except Exception:
        logger.exception("Failed to read event store")
        return 2

    drift = detect_drift(
        events,
        min_queries=args.min_queries,
        min_misses=args.min_misses,
    )
    alerts = generate_alerts(drift)
    suggestions = suggest_documents(alerts)

    payload = json.dumps(suggestions, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        logger.info("Suggestions written to %s (%d topics)", args.output, len(suggestions))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
