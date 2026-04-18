from __future__ import annotations

import json
from pathlib import Path

from evaluation.metrics import compute_metrics
from evaluation.ocr_check import check_ocr_presence


def run_eval(pipeline, eval_path: Path, data_dir: Path | None = None, strict: bool = False) -> dict:
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    tests = data.get("queries", [])
    results: list[dict] = []

    if strict and data_dir is None:
        raise ValueError("strict eval requires data_dir for OCR precheck")

    for item in tests:
        result = pipeline.run(item["query"], query_id=f"eval-{len(results) + 1}")
        passed = True
        failure_reasons = []

        actual_method = getattr(result, "intent_method", None)
        intent_correct = result.intent == item["expected_intent"]

        if not intent_correct:
            passed = False
            failure_reasons.append(
                f"intent mismatch: expected {item['expected_intent']}, got {result.intent}"
            )

        if "expected_method" in item and actual_method != item["expected_method"]:
            passed = False
            failure_reasons.append(
                f"method mismatch: expected {item['expected_method']}, got {actual_method}"
            )

        if item.get("must_be_grounded", True) and not result.grounded:
            passed = False
            failure_reasons.append("not grounded when required")

        for phrase in item.get("must_not_contain", []):
            if phrase.lower() in result.answer.lower():
                passed = False
                failure_reasons.append(f"contains forbidden phrase: '{phrase}'")

        if "expected_answer_exact" in item and result.answer != item["expected_answer_exact"]:
            passed = False
            failure_reasons.append(
                f"answer mismatch: expected '{item['expected_answer_exact']}', got '{result.answer}'"
            )

        if "expected_answer_contains" in item:
            for term in item["expected_answer_contains"]:
                if term.lower() not in result.answer.lower():
                    passed = False
                    failure_reasons.append(f"missing expected term: '{term}'")

        if "expected_failure_type" in item:
            expected = item["expected_failure_type"]
            if expected is not None and result.failure_type != expected:
                passed = False
                failure_reasons.append(
                    f"failure_type mismatch: expected {expected}, got {result.failure_type}"
                )
            elif expected is None and result.failure_type is not None:
                passed = False
                failure_reasons.append(f"unexpected failure_type: {result.failure_type}")

        expected_refusal = item.get(
            "expected_refusal",
            item.get("expected_answer_exact") == "Insufficient data."
        )

        results.append(
            {
                "query": item["query"],
                "answer": result.answer,
                "intent": result.intent,
                "intent_method": actual_method,
                "grounded": result.grounded,
                "failure_type": result.failure_type,
                "passed": passed,
                "failure_reasons": failure_reasons,
                "latency_ms": result.latency_ms,
                "intent_correct": intent_correct,
                "expected_intent": item["expected_intent"],
                "expected_refusal": expected_refusal,
            }
        )

    ocr_result = {"ocr_presence_check": True, "pdf_status": {}}
    if data_dir is not None:
        ocr_result = check_ocr_presence(data_dir)
    elif strict:
        ocr_result = {"ocr_presence_check": False, "pdf_status": {"error": "OCR precheck not run"}}

    metrics = compute_metrics(results, ocr_presence_check=ocr_result["ocr_presence_check"])
    metrics["pdf_status"] = ocr_result["pdf_status"]

    return {"metrics": metrics, "results": results}
