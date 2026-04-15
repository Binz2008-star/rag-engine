"""Simple eval runner for RAG queries."""

import json
import sys
from pathlib import Path

from app.rag_pipeline import RagPipeline

EVAL_QUERIES_PATH = Path(__file__).parent / "tests" / "eval_queries.json"


def check_result(result, test: dict) -> tuple[bool, list[str]]:
    """Check if result matches expected criteria. Returns (passed, failure_reasons)."""
    answer = result.answer
    failure_reasons = []

    if "expected_exact" in test:
        if answer != test["expected_exact"]:
            failure_reasons.append("wrong_answer")
        return (answer == test["expected_exact"], failure_reasons)

    if "expected_contains" in test:
        missing_terms = []
        for term in test["expected_contains"]:
            if term.lower() not in answer.lower():
                missing_terms.append(term)
        if missing_terms:
            failure_reasons.append(f"missing_terms: {missing_terms}")
            # Attribution: if terms are missing, check if it's context or generation
            # This is a heuristic - real attribution would need deeper analysis
            failure_reasons.append("generation_omitted_supported_fact")
        return (len(missing_terms) == 0, failure_reasons)

    if "expected_source" in test:
        expected = test["expected_source"]
        sources = [s["source"] for s in result.sources]
        source_match = any(expected in src for src in sources)
        if not source_match:
            failure_reasons.append(f"wrong_source_family: expected {expected}, got {sources}")
            failure_reasons.append("wrong_intent")
        return (source_match, failure_reasons)

    return (True, failure_reasons)


def main():
    """Run evaluation queries."""
    with open(EVAL_QUERIES_PATH, "r", encoding="utf-8") as f:
        tests = json.load(f)

    pipeline = RagPipeline()

    try:
        print("Building index...")
        pipeline.build_index()

        passed = 0
        failed = 0

        for i, test in enumerate(tests, 1):
            question = test["question"]
            print(f"\n[{i}/{len(tests)}] {question}")

            result = pipeline.query(question)
            print(f"  Answer: {result.answer[:100]}{'...' if len(result.answer) > 100 else ''}")
            print(f"  Sources: {[s['source'] for s in result.sources]}")

            passed_check, failure_reasons = check_result(result, test)
            if passed_check:
                print("  PASS")
                passed += 1
            else:
                print("  FAIL")
                for reason in failure_reasons:
                    print(f"    {reason}")
                if "expected_exact" in test:
                    print(f"    Expected: {test['expected_exact']}")
                elif "expected_source" in test:
                    print(f"    Expected source: {test['expected_source']}")
                failed += 1

        print(f"\n{'='*70}")
        print(f"Results: {passed}/{len(tests)} passed, {failed} failed")
        print(f"{'='*70}")

        return 0 if failed == 0 else 1

    finally:
        pipeline.close()


if __name__ == "__main__":
    sys.exit(main())
