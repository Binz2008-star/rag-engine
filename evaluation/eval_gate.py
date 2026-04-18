from __future__ import annotations


def gate(metrics: dict) -> dict:
    failed = []

    if metrics.get("pass_rate", 0.0) < 0.95:
        failed.append("pass_rate")
    if metrics.get("hallucination_rate", 1.0) != 0.0:
        failed.append("hallucination_rate")
    if metrics.get("refusal_accuracy", 0.0) < 1.0:
        failed.append("refusal_accuracy")
    if metrics.get("domain_accuracy", 0.0) < 0.95:
        failed.append("domain_accuracy")
    if metrics.get("ocr_presence_check", False) is not True:
        failed.append("ocr_presence_check")

    return {
        "decision": "PROMOTE" if not failed else "REJECT",
        "failed_checks": failed,
        "metrics": metrics,
    }
