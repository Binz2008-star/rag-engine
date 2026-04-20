"""Unit tests for the canonical promotion gate (`evaluation/eval_gate.py`)."""

from __future__ import annotations

import pytest

from evaluation.eval_gate import gate

ALL_CHECKS = {
    "pass_rate",
    "hallucination_rate",
    "refusal_accuracy",
    "domain_accuracy",
    "ocr_presence_check",
}


def _base_metrics(**overrides) -> dict:
    """Return a metrics dict that PROMOTES by default."""
    metrics = {
        "pass_rate": 1.0,
        "hallucination_rate": 0.0,
        "refusal_accuracy": 1.0,
        "domain_accuracy": 1.0,
        "ocr_presence_check": True,
    }
    metrics.update(overrides)
    return metrics


# ── Happy path ─────────────────────────────────────────────────────────────

def test_gate_promotes_when_all_checks_pass():
    result = gate(_base_metrics())
    assert result["decision"] == "PROMOTE"
    assert result["failed_checks"] == []


def test_gate_accepts_pass_rate_exactly_at_threshold():
    result = gate(_base_metrics(pass_rate=0.95))
    assert result["decision"] == "PROMOTE"


def test_gate_accepts_domain_accuracy_exactly_at_threshold():
    result = gate(_base_metrics(domain_accuracy=0.95))
    assert result["decision"] == "PROMOTE"


# ── Individual failure conditions ──────────────────────────────────────────

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pass_rate",          0.94),
        ("hallucination_rate", 0.001),
        ("refusal_accuracy",   0.99),
        ("domain_accuracy",    0.94),
        ("ocr_presence_check", False),
    ],
)
def test_gate_rejects_each_failed_check(field, value):
    result = gate(_base_metrics(**{field: value}))
    assert result["decision"] == "REJECT"
    assert field in result["failed_checks"]


def test_gate_reports_all_failed_checks():
    result = gate(_base_metrics(
        pass_rate=0.5,
        hallucination_rate=0.1,
        refusal_accuracy=0.5,
        domain_accuracy=0.5,
        ocr_presence_check=False,
    ))
    assert result["decision"] == "REJECT"
    assert set(result["failed_checks"]) == ALL_CHECKS


def test_gate_rejects_missing_metrics():
    result = gate({})
    assert result["decision"] == "REJECT"
    assert set(result["failed_checks"]) == ALL_CHECKS


# ── Contract hardening: invalid types / ranges must REJECT (not crash) ─────

@pytest.mark.parametrize(
    ("field", "value"),
    [
        # None → REJECT (no TypeError)
        ("pass_rate",          None),
        ("hallucination_rate", None),
        ("refusal_accuracy",   None),
        ("domain_accuracy",    None),
        # Out of range (> 1.0) → REJECT
        ("pass_rate",          1.5),
        ("hallucination_rate", 2.0),
        ("refusal_accuracy",   1.1),
        ("domain_accuracy",    1.01),
        # Out of range (< 0.0) → REJECT
        ("pass_rate",          -0.1),
        ("hallucination_rate", -0.5),
        ("refusal_accuracy",   -0.01),
        ("domain_accuracy",    -1.0),
        # Wrong types → REJECT
        ("pass_rate",          "1.0"),
        ("hallucination_rate", "0"),
        ("refusal_accuracy",   [1.0]),
        ("domain_accuracy",    {"value": 1.0}),
        # Booleans are NOT rates
        ("pass_rate",          True),
        ("hallucination_rate", False),
    ],
)
def test_gate_rejects_invalid_rate_values(field, value):
    result = gate(_base_metrics(**{field: value}))
    assert result["decision"] == "REJECT"
    assert field in result["failed_checks"]


@pytest.mark.parametrize(
    "value",
    [1, 0, "true", "True", "yes", 1.0, [True], {"ok": True}, None],
)
def test_gate_rejects_non_strict_ocr_values(value):
    """ocr_presence_check must be `is True` — no truthy substitutes."""
    result = gate(_base_metrics(ocr_presence_check=value))
    assert result["decision"] == "REJECT"
    assert "ocr_presence_check" in result["failed_checks"]


# ── Return-shape contract ──────────────────────────────────────────────────

def test_gate_return_shape():
    metrics = _base_metrics()
    result = gate(metrics)
    assert set(result.keys()) == {"decision", "failed_checks", "metrics"}
    assert result["metrics"] is metrics
    assert result["decision"] in {"PROMOTE", "REJECT"}
    assert isinstance(result["failed_checks"], list)


# ── Killer-query enforcement ───────────────────────────────────────────────

def _killer_result(passed: bool, killer: bool = True) -> dict:
    return {"query": "dangerous", "passed": passed, "killer": killer}


def test_gate_promotes_when_all_killers_pass():
    result = gate(_base_metrics(), results=[_killer_result(passed=True)])
    assert result["decision"] == "PROMOTE"
    assert "killer_failure" not in result["failed_checks"]


def test_gate_rejects_when_any_killer_fails():
    results = [_killer_result(passed=True), _killer_result(passed=False)]
    result = gate(_base_metrics(), results=results)
    assert result["decision"] == "REJECT"
    assert "killer_failure" in result["failed_checks"]


def test_gate_ignores_non_killer_failures():
    """A failing non-killer row must NOT trigger killer_failure."""
    result = gate(
        _base_metrics(),
        results=[{"query": "x", "passed": False, "killer": False}],
    )
    assert "killer_failure" not in result["failed_checks"]


def test_gate_backward_compatible_without_results():
    """Old callers that don't pass results must still work."""
    result = gate(_base_metrics())
    assert result["decision"] == "PROMOTE"
    assert "killer_failure" not in result["failed_checks"]


def test_gate_killer_stacks_with_other_failures():
    result = gate(
        _base_metrics(pass_rate=0.5),
        results=[_killer_result(passed=False)],
    )
    assert result["decision"] == "REJECT"
    assert "pass_rate" in result["failed_checks"]
    assert "killer_failure" in result["failed_checks"]


@pytest.mark.parametrize(
    "bad_results",
    [
        [None],
        ["not a dict"],
        [{"passed": True}],   # missing killer flag → not a killer row
    ],
)
def test_gate_tolerates_non_killer_malformed_rows(bad_results):
    """Rows that are not killer (or are entirely malformed) must not crash or flag."""
    result = gate(_base_metrics(), results=bad_results)
    assert "killer_failure" not in result["failed_checks"]


def test_gate_rejects_killer_row_missing_passed_field():
    """Fail-closed: a killer row without an explicit `passed: True` must REJECT."""
    result = gate(_base_metrics(), results=[{"killer": True}])
    assert result["decision"] == "REJECT"
    assert "killer_failure" in result["failed_checks"]
