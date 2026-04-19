"""
Canonical promotion gate.

Policy:
    pass_rate            >= 0.95   and in [0.0, 1.0]
    hallucination_rate   == 0.0    and in [0.0, 1.0]
    refusal_accuracy     == 1.0    and in [0.0, 1.0]
    domain_accuracy      >= 0.95   and in [0.0, 1.0]
    ocr_presence_check   is True   (strict identity, not truthy)
    killer_queries       every result with `killer: true` must be `passed: true`

The gate is **fail-closed**: any missing, non-numeric, out-of-range,
or wrongly-typed value counts as a rejection for that check.

`results` is optional for backward compatibility; when provided, killer
queries are enforced as an additional hard-fail signal.
"""
from __future__ import annotations

from typing import Any, Iterable

_RATE_CHECKS: tuple[tuple[str, float, str], ...] = (
    ("pass_rate",          0.95, ">="),
    ("hallucination_rate", 0.0,  "=="),
    ("refusal_accuracy",   1.0,  "=="),
    ("domain_accuracy",    0.95, ">="),
)

_KILLER_FAILURE_CHECK = "killer_failure"


def _is_valid_rate(value: Any) -> bool:
    """A rate is valid only if it is a non-bool int/float within [0.0, 1.0]."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return 0.0 <= float(value) <= 1.0


def _rate_passes(value: Any, threshold: float, op: str) -> bool:
    if not _is_valid_rate(value):
        return False
    numeric = float(value)
    if op == ">=":
        return numeric >= threshold
    if op == "==":
        return numeric == threshold
    return False


def _check_killers(results: Iterable[dict] | None) -> list[str]:
    """Return [_KILLER_FAILURE_CHECK] if any killer result did not pass."""
    if not results:
        return []
    for row in results:
        if not isinstance(row, dict):
            continue
        if row.get("killer") is True and row.get("passed") is not True:
            return [_KILLER_FAILURE_CHECK]
    return []


def gate(metrics: dict, results: Iterable[dict] | None = None) -> dict:
    failed: list[str] = []

    for field, threshold, op in _RATE_CHECKS:
        if not _rate_passes(metrics.get(field), threshold, op):
            failed.append(field)

    # ocr_presence_check must be the boolean True — not truthy, not an int.
    if metrics.get("ocr_presence_check") is not True:
        failed.append("ocr_presence_check")

    failed.extend(_check_killers(results))

    return {
        "decision": "PROMOTE" if not failed else "REJECT",
        "failed_checks": failed,
        "metrics": metrics,
    }
