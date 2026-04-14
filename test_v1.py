"""Test RAG queries with v1 architecture."""

import sys
import time
from app.rag_pipeline import RagPipeline

def test_query(pipeline: RagPipeline, query: str) -> dict:
    """Run a single test query."""
    print(f"\n{'='*70}")
    print(f"QUERY: {query}")
    print(f"{'='*70}")
    
    t0 = time.perf_counter()
    response = pipeline.query(query)
    t1 = time.perf_counter()
    
    print(f"\n>>> ANSWER:")
    print(response.answer)
    print(f"\n>>> SOURCES:")
    for src in response.sources:
        print(f"  - {src}")
    print(f"\n>>> TIMING:")
    print(f"  Retrieval: {response.retrieval_time:.3f}s")
    print(f"  Generation: {response.generation_time:.3f}s")
    print(f"  Total: {t1 - t0:.3f}s")
    
    return {
        "query": query,
        "answer": response.answer,
        "sources": response.sources,
        "retrieval_time": response.retrieval_time,
        "generation_time": response.generation_time,
    }

def main():
    """Run three test queries."""
    pipeline = RagPipeline()
    
    try:
        print("Building index...")
        pipeline.build_index()
        
        queries = [
            "Who is Robin Edwan?",
            "What role is the CV tailored for?",
            "What is the GDP of Japan?",
        ]
        
        results = []
        for query in queries:
            result = test_query(pipeline, query)
            results.append(result)
        
        # Summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        for i, result in enumerate(results, 1):
            print(f"\nQuery {i}: {result['query']}")
            print(f"  Answer length: {len(result['answer'])} chars")
            print(f"  Sources: {len(result['sources'])}")
            print(f"  Answer: {result['answer'][:100]}..." if len(result['answer']) > 100 else f"  Answer: {result['answer']}")
        
    finally:
        pipeline.close()

if __name__ == "__main__":
    main()
