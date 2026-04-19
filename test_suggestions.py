"""Unit tests for `analysis/suggestions.py`."""

from __future__ import annotations

from analysis.suggestions import suggest_documents


def _alert(
    topic: str,
    *,
    action: str = "add_documents",
    drift_score: float = 0.7,
    top_missing_source: str | None = None,
) -> dict:
    evidence: dict = {"drift_score": drift_score, "miss_count": 5}
    if top_missing_source is not None:
        evidence["top_missing_source"] = top_missing_source
    return {
        "type": "knowledge_gap" if action == "add_documents" else "degradation",
        "topic": topic,
        "priority": "high" if action == "add_documents" else "medium",
        "action": action,
        "evidence": evidence,
    }


def test_suggest_documents_from_alert():
    alerts = [_alert(
        "environmental_permits",
        drift_score=0.7,
        top_missing_source="municipal_regulations_2024.pdf",
    )]
    result = suggest_documents(alerts)

    assert len(result) == 1
    rec = result[0]
    assert rec["topic"] == "environmental_permits"
    assert "municipal_regulations_2024.pdf" in rec["suggested_documents"]
    assert rec["confidence"] == 0.7
    assert rec["source_hint"] == "top_missing_source"


def test_suggest_documents_primary_comes_first():
    alerts = [_alert(
        "environmental_permits",
        top_missing_source="custom_regulation.pdf",
    )]
    result = suggest_documents(alerts)

    # Primary signal must lead, catalog fallbacks follow
    assert result[0]["suggested_documents"][0] == "custom_regulation.pdf"


def test_suggest_documents_deduplicates_overlap_between_primary_and_fallback():
    # When top_missing_source is already in the catalog fallback, do not duplicate.
    alerts = [_alert(
        "environmental_permits",
        top_missing_source="municipal_regulations_2024.pdf",
    )]
    result = suggest_documents(alerts)

    docs = result[0]["suggested_documents"]
    assert docs.count("municipal_regulations_2024.pdf") == 1
    assert docs[0] == "municipal_regulations_2024.pdf"


def test_suggest_documents_falls_back_to_catalog_when_no_primary():
    alerts = [_alert("wastewater", drift_score=0.6)]
    result = suggest_documents(alerts)

    assert result[0]["suggested_documents"] == ["wastewater_compliance_guide.pdf"]
    assert result[0]["source_hint"] == "topic_fallback"
    assert result[0]["confidence"] == 0.6


def test_suggest_documents_unknown_topic_with_no_primary():
    # No primary, no catalog match -> still emit record with empty list
    # so operators can see the blind spot, but mark source_hint clearly.
    alerts = [_alert("obscure_topic", drift_score=0.6)]
    result = suggest_documents(alerts)

    assert result[0]["suggested_documents"] == []
    assert result[0]["source_hint"] == "none"


def test_suggest_documents_unknown_topic_with_primary():
    # No catalog match but primary signal exists -> use it.
    alerts = [_alert(
        "obscure_topic",
        drift_score=0.55,
        top_missing_source="weird_doc.pdf",
    )]
    result = suggest_documents(alerts)

    assert result[0]["suggested_documents"] == ["weird_doc.pdf"]
    assert result[0]["source_hint"] == "top_missing_source"


def test_suggest_documents_skips_non_add_documents_actions():
    alerts = [
        _alert("audits", action="investigate", drift_score=0.3),
        _alert("permits", action="monitor", drift_score=0.1),
    ]
    assert suggest_documents(alerts) == []


def test_suggest_documents_skips_malformed_alerts():
    alerts = [
        "not_a_dict",
        {"action": "add_documents"},  # missing topic
        {"topic": "", "action": "add_documents", "evidence": {}},  # empty topic
        _alert("environmental_permits"),
    ]
    result = suggest_documents(alerts)

    assert len(result) == 1
    assert result[0]["topic"] == "environmental_permits"


def test_suggest_documents_handles_bad_drift_score_type():
    alerts = [{
        "topic": "environmental_permits",
        "action": "add_documents",
        "evidence": {"drift_score": "not_a_number"},
    }]
    result = suggest_documents(alerts)

    assert result[0]["confidence"] == 0.0


def test_suggest_documents_preserves_alert_order():
    alerts = [
        _alert("environmental_permits", drift_score=0.6),
        _alert("wastewater", drift_score=0.8),
        _alert("cv", drift_score=0.5),
    ]
    result = suggest_documents(alerts)

    assert [r["topic"] for r in result] == ["environmental_permits", "wastewater", "cv"]


def test_suggest_documents_empty_input():
    assert suggest_documents([]) == []
