from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = {
    "version",
    "ts",
    "event_type",
    "query_id",
}

ALLOWED_EVENT_TYPES = {
    "query_received",
    "route_decision",
    "retrieval_result",
    "retrieval_debug",
    "generation_result",
    "failure",
    "query_completed",
    "query_failed",
    "training_sample",
    "model_published",
    "evaluation_result",
}


def validate_event(event: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(event.keys())
    if missing:
        raise ValueError(f"Event missing fields: {sorted(missing)}")
    if event["event_type"] not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event['event_type']}")
