from __future__ import annotations


def gate(metrics: dict) -> str:
    if metrics.get("pass_rate", 0.0) < 0.85 or metrics.get("hallucination_rate", 1.0) > 0.05:
        return "REJECT"
    return "PROMOTE"
