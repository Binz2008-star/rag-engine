from __future__ import annotations


def compute_metrics(results: list[dict], ocr_presence_check: bool = False) -> dict:
    total = len(results)
    passed = sum(1 for row in results if row.get("passed") is True)
    hallucinations = sum(1 for row in results if row.get("failure_type") == "hallucination")
    retrieval_misses = sum(1 for row in results if row.get("failure_type") == "retrieval_miss")

    refusal_rows = [row for row in results if row.get("expected_refusal") is True]
    refusal_correct = sum(
        1 for row in refusal_rows
        if str(row.get("answer", "")).strip().lower() == "insufficient data."
    )

    domain_rows = [row for row in results if row.get("expected_intent") in {"eco", "cv"}]
    domain_correct = sum(1 for row in domain_rows if row.get("intent_correct") is True)

    avg_latency_ms = round(
        sum(float(row.get("latency_ms", 0)) for row in results) / total, 1
    ) if total else 0.0

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "hallucination_rate": round(hallucinations / total, 3) if total else 0.0,
        "retrieval_miss_rate": round(retrieval_misses / total, 3) if total else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "refusal_accuracy": round(refusal_correct / len(refusal_rows), 3) if refusal_rows else 1.0,
        "domain_accuracy": round(domain_correct / len(domain_rows), 3) if domain_rows else 0.0,
        "ocr_presence_check": ocr_presence_check,
    }
