"""Simple eval runner for RAG queries."""

import json
import sys
from pathlib import Path

from app.rag_pipeline import RagPipeline

EVAL_QUERIES_PATH = Path(__file__).parent / "tests" / "eval_queries.json"


def check_result(result, test: dict) -> bool:
    """Check if result matches expected criteria."""
    answer = result.answer

    if "expected_exact" in test:
        return answer == test["expected_exact"]

    if "expected_contains" in test:
        for term in test["expected_contains"]:
            if term.lower() not in answer.lower():
                return False
        return True

    if "expected_source" in test:
        expected = test["expected_source"]
        sources = [s["source"] for s in result.sources]
        return any(expected in src for src in sources)

    return True


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

            if check_result(result, test):
                print("  PASS")
                passed += 1
            else:
                print("  FAIL")
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
