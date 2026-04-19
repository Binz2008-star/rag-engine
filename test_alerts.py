"""Unit tests for `analysis/alerts.py`."""

from __future__ import annotations

from analysis.alerts import generate_alerts


def _drift(
    topic: str,
    drift_score: float,
    miss_count: int,
    *,
    top_missing_source: str | None = None,
) -> dict:
    return {
        "topic": topic,
        "drift_score": drift_score,
        "miss_count": miss_count,
        "query_count": 10,
        "action": "add_documents",
        "top_missing_source": top_missing_source,
    }


def test_generate_alerts_high_priority():
    drift = [_drift("permits", 0.6, 5, top_missing_source="regulations.pdf")]
    alerts = generate_alerts(drift)

    assert len(alerts) == 1
    a = alerts[0]
    assert a["type"] == "knowledge_gap"
    assert a["topic"] == "permits"
    assert a["priority"] == "high"
    assert a["action"] == "add_documents"
    assert a["evidence"]["drift_score"] == 0.6
    assert a["evidence"]["miss_count"] == 5
    assert a["evidence"]["top_missing_source"] == "regulations.pdf"


def test_generate_alerts_medium_priority():
    drift = [_drift("audits", 0.3, 4)]
    alerts = generate_alerts(drift)

    assert len(alerts) == 1
    a = alerts[0]
    assert a["type"] == "degradation"
    assert a["priority"] == "medium"
    assert a["action"] == "investigate"
    # Medium-priority alerts intentionally omit top_missing_source to
    # signal that the actionable unit is investigation, not document add.
    assert "top_missing_source" not in a["evidence"]


def test_generate_alerts_filters_below_threshold():
    drift = [
        _drift("low_signal_a", 0.1, 1),
        _drift("low_signal_b", 0.24, 2),
    ]
    assert generate_alerts(drift) == []


def test_generate_alerts_respects_min_misses_for_high():
    # drift_score qualifies for high, but miss_count is below threshold.
    # Should fall back to medium, not high.
    drift = [_drift("tenders", 0.8, 2)]
    alerts = generate_alerts(drift)

    assert len(alerts) == 1
    assert alerts[0]["priority"] == "medium"
    assert alerts[0]["action"] == "investigate"


def test_generate_alerts_sorts_high_before_medium():
    drift = [
        _drift("medium_topic", 0.3, 4),
        _drift("high_topic", 0.6, 5, top_missing_source="x.pdf"),
    ]
    alerts = generate_alerts(drift)

    assert [a["priority"] for a in alerts] == ["high", "medium"]
    assert alerts[0]["topic"] == "high_topic"


def test_generate_alerts_sort_is_deterministic_within_priority():
    drift = [
        _drift("topic_b", 0.6, 5),
        _drift("topic_a", 0.8, 5),
        _drift("topic_c", 0.6, 5),
    ]
    alerts = generate_alerts(drift)

    # Within high priority: drift_score desc, then topic asc
    assert [a["topic"] for a in alerts] == ["topic_a", "topic_b", "topic_c"]


def test_generate_alerts_skips_malformed_records():
    drift = [
        {"topic": "ok", "drift_score": 0.7, "miss_count": 5},
        {"topic": "bad_missing_score", "miss_count": 5},
        {"drift_score": 0.7, "miss_count": 5},  # missing topic
        {"topic": "bad_type", "drift_score": "not_a_number", "miss_count": 5},
    ]
    alerts = generate_alerts(drift)

    assert len(alerts) == 1
    assert alerts[0]["topic"] == "ok"


def test_generate_alerts_empty_input():
    assert generate_alerts([]) == []


def test_generate_alerts_high_without_top_missing_source():
    drift = [_drift("permits", 0.6, 5, top_missing_source=None)]
    alerts = generate_alerts(drift)

    assert len(alerts) == 1
    # Field is omitted entirely when source is unavailable, rather than
    # emitting a misleading null that downstream consumers might log.
    assert "top_missing_source" not in alerts[0]["evidence"]
