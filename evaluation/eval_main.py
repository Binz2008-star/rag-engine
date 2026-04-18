from __future__ import annotations

import json
from pathlib import Path

from evaluation.metrics import compute_metrics


def run_eval(pipeline, eval_path: Path) -> dict:
    tests = json.loads(eval_path.read_text(encoding="utf-8"))
    results: list[dict] = []

    for item in tests:
        result = pipeline.run(item["question"], query_id=f"eval-{len(results) + 1}")
        answer = result.answer
        passed = True

        if "expected_exact" in item and answer != item["expected_exact"]:
            passed = False
        if "expected_contains" in item:
            for term in item["expected_contains"]:
                if term.lower() not in answer.lower():
                    passed = False

        results.append(
            {
                "question": item["question"],
                "answer": answer,
                "passed": passed,
                "failure_type": result.failure_type,
            }
        )

    metrics = compute_metrics(results)
    return {"metrics": metrics, "results": results}
