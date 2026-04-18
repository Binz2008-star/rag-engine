from __future__ import annotations


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for row in results if row.get("passed"))
    hallucinations = sum(1 for row in results if row.get("failure_type") == "hallucination")
    refusals = sum(1 for row in results if row.get("answer") == "Insufficient data.")
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "hallucination_rate": round(hallucinations / total, 3) if total else 0.0,
        "refusal_rate": round(refusals / total, 3) if total else 0.0,
    }
