"""Run critical RAG validation tests."""

import sys
import time
from rag_optimized import OllamaClient, VectorStore, _load_or_build, retrieve_context, generate_response


def run_test(query: str, expected_contains: str | None = None, expect_failure: bool = False):
    """Run a single test query."""
    print(f"\n{'='*70}")
    print(f"TEST: {query}")
    print(f"{'='*70}")
    
    client = OllamaClient()
    store = _load_or_build(client)
    
    t0 = time.perf_counter()
    context_chunks = retrieve_context(store, query, client)
    t1 = time.perf_counter()
    
    print(f"\n>>> RETRIEVAL: {t1-t0:.2f}s, {len(context_chunks)} chunks")
    
    if not context_chunks:
        print("[FAIL] No chunks retrieved")
        return False
    
    answer = generate_response(query, context_chunks, client)
    t2 = time.perf_counter()
    
    print(f"\n>>> ANSWER ({t2-t1:.2f}s):")
    print(answer)
    
    # Validation
    if expect_failure:
        if "insufficient" in answer.lower() or "don't know" in answer.lower():
            print("\n[PASS] Correctly refused to answer")
            return True
        else:
            print("\n[FAIL] Should have refused but gave an answer")
            return False
    
    if expected_contains and expected_contains.lower() not in answer.lower():
        print(f"\n[FAIL] Expected answer to contain: '{expected_contains}'")
        return False
    
    print("\n[PASS] Basic response validation passed")
    return True


def main():
    """Run all critical tests."""
    results = []
    
    # Test A: Known answer (requires your CV data)
    results.append(("A (Known Answer)", run_test(
        "Who is Robin Edwan?",
        expected_contains="Robin"
    )))
    
    # Test B: Specific retrieval (requires certificate data)
    results.append(("B (Specific)", run_test(
        "What certifications are listed?",
        expected_contains="certification"  # or actual cert names if known
    )))
    
    # Test C: Failure case - MOST IMPORTANT
    results.append(("C (Failure Case)", run_test(
        "What is the GDP of Japan?",
        expect_failure=True
    )))
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for _, r in results if r)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
    print(f"\nTotal: {passed}/{len(results)} passed")
    
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
