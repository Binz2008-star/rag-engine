"""Unit tests for `analysis/drift_detector.py`."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import pytest

from analysis.drift_detector import (
    _extract_topic,
    _is_miss,
    _is_refusal,
    _pick_top_source,
    detect_drift,
)
from events.store import EventStore


def _event(
    normalized_query: str,
    *,
    event_type: str = "generation_result",
    failure_type: str | None = None,
    retrieval: list[dict] | None = None,
    answer: str = "ok",
) -> dict:
    return {
        "event_type": event_type,
        "query_id": "q",
        "normalized_query": normalized_query,
        "query": normalized_query,
        "retrieval": retrieval if retrieval is not None else [{"doc_id": "d1", "score": 0.9, "source": "x"}],
        "failure_type": failure_type,
        "answer": answer,
    }


def test_extract_topic_prefers_domain_phrase():
    assert _extract_topic("what environmental permit is required") == "environmental_permits"
    assert _extract_topic("grease trap cleaning frequency") == "grease_management"
    assert _extract_topic("waste management policy") == "waste_management"


def test_extract_topic_falls_back_to_first_non_stopword():
    assert _extract_topic("what is the reactor capacity") == "reactor"


def test_extract_topic_handles_empty_and_unknown():
    assert _extract_topic("") == "_unknown"
    assert _extract_topic("the a an of") == "_unknown"


def test_is_miss_detects_failure_type():
    # Test with specific failure types - any non-None failure_type should be detected as miss
    assert _is_miss(_event("q", failure_type="retrieval_empty")) is True
    assert _is_miss(_event("q", failure_type="grounding_reject")) is True
    assert _is_miss(_event("q", failure_type="term_overlap_miss")) is True


def test_is_miss_detects_empty_retrieval():
    assert _is_miss(_event("q", retrieval=[])) is True


def test_is_miss_detects_refusal_answer():
    # Retrieval exists, no failure_type, but answer is canonical refusal
    assert _is_miss(_event("q", answer="Insufficient data.")) is True
    assert _is_miss(_event("q", answer="insufficient data")) is True
    assert _is_miss(_event("q", answer="  Insufficient Data.  ")) is True


def test_is_miss_false_on_healthy_event():
    assert _is_miss(_event("q")) is False


def test_is_refusal_rejects_non_strings_and_normal_answers():
    assert _is_refusal(None) is False
    assert _is_refusal(123) is False
    assert _is_refusal("The answer is 42.") is False


def test_extract_topic_longest_phrase_wins():
    # "environmental permit" (20 chars) must beat "wastewater" (10 chars)
    # even though both substrings are present.
    assert (
        _extract_topic("environmental permit for wastewater facility")
        == "environmental_permits"
    )
    # "waste management" must beat "waste"
    assert _extract_topic("waste management plan") == "waste_management"


def test_pick_top_source_deterministic_tie_break():
    counter = Counter({"a.pdf": 3, "b.pdf": 3, "c.pdf": 1})
    # Ties resolve alphabetically
    assert _pick_top_source(counter) == "a.pdf"


def test_pick_top_source_returns_none_on_empty():
    assert _pick_top_source(Counter()) is None


def test_detect_drift_skips_non_terminal_events():
    events = [_event("environmental permit question", event_type="route_decision", retrieval=[])] * 10
    assert detect_drift(events, min_queries=1) == []


def test_detect_drift_respects_min_queries():
    events = [_event("environmental permit one", retrieval=[])] * 2
    assert detect_drift(events, min_queries=5) == []


def test_detect_drift_aggregates_and_sorts():
    events = (
        [_event("environmental permit x", retrieval=[])] * 8
        + [_event("environmental permit y")] * 2
        + [_event("grease trap a", retrieval=[])] * 3
        + [_event("grease trap b")] * 3
    )

    records = detect_drift(events, min_queries=5, min_misses=3)

    assert len(records) == 2
    assert records[0]["topic"] == "environmental_permits"
    assert records[0]["query_count"] == 10
    assert records[0]["miss_count"] == 8
    assert records[0]["drift_score"] == pytest.approx(0.8)
    assert records[0]["action"] == "add_documents"
    # All misses had empty retrieval -> no source to report
    assert records[0]["top_missing_source"] is None

    assert records[1]["topic"] == "grease_management"
    assert records[1]["drift_score"] == pytest.approx(0.5)
    assert records[1]["action"] == "add_documents"
    assert records[1]["top_missing_source"] is None


def test_detect_drift_reports_top_missing_source():
    # 6 misses: 4 cite "municipal_regulations_2024.pdf", 2 cite "eco_profile.pdf"
    # Plus 4 healthy queries.
    miss_with_municipal = _event(
        "environmental permit scope",
        failure_type="retrieval_empty",
        retrieval=[{"doc_id": "d1", "score": 0.3, "source": "municipal_regulations_2024.pdf"}],
        answer="Insufficient data.",
    )
    miss_with_eco = _event(
        "environmental permit coverage",
        failure_type="retrieval_empty",
        retrieval=[{"doc_id": "d2", "score": 0.25, "source": "eco_profile.pdf"}],
        answer="Insufficient data.",
    )
    healthy = _event("environmental permit ok")

    events = [miss_with_municipal] * 4 + [miss_with_eco] * 2 + [healthy] * 4

    records = detect_drift(events, min_queries=5, min_misses=3)

    assert len(records) == 1
    rec = records[0]
    assert rec["topic"] == "environmental_permits"
    assert rec["query_count"] == 10
    assert rec["miss_count"] == 6
    assert rec["drift_score"] == pytest.approx(0.6)
    assert rec["action"] == "add_documents"
    assert rec["top_missing_source"] == "municipal_regulations_2024.pdf"


def test_detect_drift_counts_refusal_with_retrieval_as_miss():
    # Retrieval non-empty, no failure_type, but answer is a refusal.
    # This is the exact case the tightening targeted.
    refusal_events = [
        _event(
            "audit scope",
            retrieval=[{"doc_id": "d1", "score": 0.2, "source": "compliance_guide.pdf"}],
            answer="Insufficient data.",
        )
    ] * 5

    records = detect_drift(refusal_events, min_queries=5, min_misses=3)

    assert len(records) == 1
    assert records[0]["topic"] == "audits"
    assert records[0]["miss_count"] == 5
    assert records[0]["top_missing_source"] == "compliance_guide.pdf"


def test_detect_drift_action_thresholds():
    # drift 0.3 with >=3 misses => investigate
    events = (
        [_event("audit one", retrieval=[])] * 3
        + [_event("audit two")] * 7
    )
    records = detect_drift(events, min_queries=5, min_misses=3)
    assert records[0]["action"] == "investigate"
    assert records[0]["drift_score"] == pytest.approx(0.3)


def test_detect_drift_action_monitor_when_miss_count_low():
    # High drift score but only 2 misses -> monitor (below min_misses)
    events = (
        [_event("tender alpha", retrieval=[])] * 2
        + [_event("tender beta")] * 3
    )
    records = detect_drift(events, min_queries=5, min_misses=3)
    assert records[0]["topic"] == "tenders"
    assert records[0]["action"] == "monitor"


def test_detect_drift_threshold_filter():
    events = [_event("cv update one")] * 10
    # no misses -> drift 0.0, filtered out when threshold > 0
    assert detect_drift(events, min_queries=5, drift_threshold=0.01) == []


def test_detect_drift_is_deterministic():
    events = (
        [_event("waste management a", retrieval=[])] * 4
        + [_event("waste management b")] * 1
        + [_event("audit x", retrieval=[])] * 4
        + [_event("audit y")] * 1
    )
    a = detect_drift(events, min_queries=5, min_misses=3)
    b = detect_drift(events, min_queries=5, min_misses=3)
    assert a == b


def test_detect_drift_validates_args():
    with pytest.raises(ValueError):
        detect_drift([], min_queries=0)
    with pytest.raises(ValueError):
        detect_drift([], drift_threshold=1.5)


def test_detect_drift_falls_back_to_raw_query_when_normalized_missing():
    events = [
        {
            "event_type": "generation_result",
            "query_id": "q",
            "query": "Environmental Permit Required?",
            "retrieval": [],
            "failure_type": None,
        }
    ] * 5
    records = detect_drift(events, min_queries=5, min_misses=3)
    assert records[0]["topic"] == "environmental_permits"
    assert records[0]["miss_count"] == 5


# ── Integration with real SQLite EventStore ────────────────────────────────


def _write_event(store: EventStore, payload: dict) -> None:
    """Write a fully-formed event honoring the schema required by EventStore."""
    event = {
        "version": "v1",
        "ts": time.time(),
        **payload,
    }
    store.write(event)


def test_drift_detector_reads_from_sqlite_store(tmp_path: Path):
    """Full round-trip: write terminal events to SQLite, read back, detect drift."""
    db_path = tmp_path / "events.db"
    store = EventStore(db_path=db_path)

    # 5 misses on 'environmental permit', 5 hits on 'cv'
    for i in range(5):
        _write_event(store, {
            "event_type": "generation_result",
            "query_id": f"miss-{i}",
            "query": "environmental permit requirements",
            "normalized_query": "environmental permit requirements",
            "retrieval": [],
            "failure_type": "retrieval_empty",
            "answer": "Insufficient data.",
        })
    for i in range(5):
        _write_event(store, {
            "event_type": "generation_result",
            "query_id": f"hit-{i}",
            "query": "what role is the cv tailored for",
            "normalized_query": "what role is the cv tailored for",
            "retrieval": [{"doc_id": "cv_1", "score": 0.9, "source": "cv.pdf"}],
            "failure_type": None,
            "answer": "Deliveroo.",
        })

    events = store.read_all()
    records = detect_drift(events, min_queries=5, min_misses=3, drift_threshold=0.01)

    # Only the drifting topic passes the threshold.
    assert len(records) == 1
    assert records[0]["topic"] == "environmental_permits"
    assert records[0]["query_count"] == 5
    assert records[0]["miss_count"] == 5
    assert records[0]["drift_score"] == pytest.approx(1.0)
    assert records[0]["action"] == "add_documents"


def test_drift_detector_ignores_non_terminal_events_in_store(tmp_path: Path):
    """route_decision / retrieval_result must not be counted."""
    db_path = tmp_path / "events.db"
    store = EventStore(db_path=db_path)

    # Write 10 route_decision events on a failing topic — should be ignored.
    for i in range(10):
        _write_event(store, {
            "event_type": "route_decision",
            "query_id": f"rd-{i}",
            "query": "environmental permit x",
            "normalized_query": "environmental permit x",
            "intent": "eco",
            "confidence": 1.0,
            "intent_method": "rule",
        })

    events = store.read_all()
    records = detect_drift(events, min_queries=1, min_misses=1)
    assert records == []
