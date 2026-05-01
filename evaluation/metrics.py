from __future__ import annotations

from evaluation.refusal import is_insufficient_response


def compute_metrics(results: list[dict], ocr_presence_check: bool = False) -> dict:
    """Compute canonical evaluation metrics over result rows.

    Args:
        results: per-query result dicts. Must carry ``passed``,
            ``failure_type``, ``expected_refusal``, ``answer``,
            ``expected_intent``, ``intent``, and ``latency_ms``. Rows
            MAY also carry a pre-computed ``intent_correct`` flag.
        ocr_presence_check: default is ``False`` on purpose — the gate
            is fail-closed on this signal, so a caller that forgets to
            pass it gets a REJECT rather than a silent pass.

    Refusal accuracy uses ``is_insufficient_response`` (semantic match)
    so training-path metrics align with ``eval_runner.py``; exact-match
    would diverge whenever the LLM paraphrases the refusal.
    """
    total = len(results)
    passed = sum(1 for row in results if row.get("passed") is True)

    # Rollup failure types into categories
    retrieval_failures = sum(
        1 for row in results
        if row.get("failure_type") in {"retrieval_empty", "retrieval_low_score", "term_overlap_miss"}
    )
    grounding_failures = sum(
        1 for row in results
        if row.get("failure_type") in {"grounding_reject", "speculative_reject"}
    )
    reasoning_failures = sum(
        1 for row in results
        if row.get("failure_type") == "reasoning_reject"
    )
    safety_failures = sum(
        1 for row in results
        if row.get("failure_type") in {"sensitive_reject", "injection_reject"}
    )
    routing_failures = sum(
        1 for row in results
        if row.get("failure_type") == "routing_miss"
    )
    translation_failures = sum(
        1 for row in results
        if row.get("failure_type") == "translation_failure"
    )

    refusal_rows = [row for row in results if row.get("expected_refusal") is True]
    refusal_correct = sum(
        1 for row in refusal_rows
        if is_insufficient_response(str(row.get("answer", "")))
    )

    domain_rows = [row for row in results if row.get("expected_intent") in {"eco", "cv"}]
    # Defensive: accept pre-computed ``intent_correct`` (produced by
    # eval_main.py) OR derive it from ``intent`` vs ``expected_intent``
    # (matches eval_runner.py TestResult.asdict() output).
    domain_correct = sum(
        1 for row in domain_rows
        if row.get("intent_correct") is True
        or (row.get("intent") and row.get("intent") == row.get("expected_intent"))
    )

    avg_latency_ms = round(
        sum(float(row.get("latency_ms", 0)) for row in results) / total, 1
    ) if total else 0.0

    # Self-correction metrics
    total_retries = sum(row.get("retry_attempts", 0) for row in results)
    corrected_queries = sum(1 for row in results if row.get("corrected") is True)
    correction_rate = round(corrected_queries / total, 3) if total else 0.0
    avg_retries = round(total_retries / total, 2) if total else 0.0

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "retrieval_failure_rate": round(retrieval_failures / total, 3) if total else 0.0,
        "grounding_failure_rate": round(grounding_failures / total, 3) if total else 0.0,
        "reasoning_failure_rate": round(reasoning_failures / total, 3) if total else 0.0,
        "safety_failure_rate": round(safety_failures / total, 3) if total else 0.0,
        "routing_failure_rate": round(routing_failures / total, 3) if total else 0.0,
        "translation_failure_rate": round(translation_failures / total, 3) if total else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "refusal_accuracy": round(refusal_correct / len(refusal_rows), 3) if refusal_rows else 1.0,
        "domain_accuracy": round(domain_correct / len(domain_rows), 3) if domain_rows else 0.0,
        "ocr_presence_check": ocr_presence_check,
        "correction_rate": correction_rate,
        "avg_retries": avg_retries,
    }
