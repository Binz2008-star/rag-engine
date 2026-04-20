"""Decision layer that converts drift signals into actionable alerts.

No transport, no scheduler, no enrichment: just a pure threshold-based
classifier that turns `detect_drift()` output into a ranked list of
alert records. Downstream consumers (Slack, dashboards, cron) attach
later and remain decoupled from the decision policy.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from analysis.drift_detector import _load_events_from_store, detect_drift

logger = logging.getLogger(__name__)

# Thresholds mirror the drift classifier so the two layers agree on what
# a "significant" miss rate looks like. Keep these as module constants,
# not CLI flags: alert policy should be reviewed, not tuned ad hoc.
_HIGH_DRIFT_SCORE = 0.5
_HIGH_MIN_MISSES = 3
_MEDIUM_DRIFT_SCORE = 0.25

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _build_alert(
    topic: str,
    drift_score: float,
    miss_count: int,
    *,
    alert_type: str,
    priority: str,
    action: str,
    top_missing_source: str | None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "drift_score": drift_score,
        "miss_count": miss_count,
    }
    if top_missing_source is not None:
        evidence["top_missing_source"] = top_missing_source
    return {
        "type": alert_type,
        "topic": topic,
        "priority": priority,
        "action": action,
        "evidence": evidence,
    }


def generate_alerts(drift: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify drift records into ranked alerts.

    Policy:
        - drift_score >= 0.5 AND miss_count >= 3 -> high / knowledge_gap / add_documents
        - drift_score >= 0.25                    -> medium / degradation / investigate
        - otherwise                              -> no alert emitted

    Records are returned sorted by priority (high first), then by drift
    score descending, then by topic for stable ordering.
    """
    alerts: list[dict[str, Any]] = []

    for record in drift:
        try:
            topic = record["topic"]
            score = float(record["drift_score"])
            misses = int(record["miss_count"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed drift record: %r", record)
            continue

        top_missing_source = record.get("top_missing_source")

        if score >= _HIGH_DRIFT_SCORE and misses >= _HIGH_MIN_MISSES:
            alerts.append(_build_alert(
                topic,
                score,
                misses,
                alert_type="knowledge_gap",
                priority="high",
                action="add_documents",
                top_missing_source=top_missing_source,
            ))
        elif score >= _MEDIUM_DRIFT_SCORE:
            alerts.append(_build_alert(
                topic,
                score,
                misses,
                alert_type="degradation",
                priority="medium",
                action="investigate",
                top_missing_source=None,
            ))

    alerts.sort(key=lambda a: (
        _PRIORITY_RANK.get(a["priority"], 99),
        -a["evidence"]["drift_score"],
        a["topic"],
    ))
    return alerts


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate actionable alerts from drift signals.")
    parser.add_argument("--min-queries", type=int, default=5, help="Minimum queries per topic for drift detection.")
    parser.add_argument("--min-misses", type=int, default=3, help="Minimum misses per topic for drift detection.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON alerts report.")
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

    payload = json.dumps(alerts, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        logger.info("Alerts written to %s (%d alerts)", args.output, len(alerts))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
