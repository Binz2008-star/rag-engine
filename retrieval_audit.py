"""Manual retrieval audit for failing queries."""
from app.rag_pipeline import RagPipeline
import json

pipeline = RagPipeline()
pipeline.build_index()

failing_queries = [
    "What is Eco company?",
    "What are Robin's main technical skills?",
    "What environmental certifications does Eco-Technology hold?",
]

print("\n=== RETRIEVAL AUDIT FOR FAILING QUERIES ===\n")

for query in failing_queries:
    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"{'='*60}")
    
    # Get retrieval before any filtering
    retrieved = pipeline.retriever.retrieve(query, pipeline.vector_store)
    
    print(f"\nTop 10 Retrieved Chunks (BEFORE filtering/rerank):")
    print(f"{'-'*60}")
    
    for rank, rc in enumerate(retrieved[:10], start=1):
        print(f"\nRank {rank}:")
        print(f"  Source: {rc.chunk.source}")
        print(f"  Score: {rc.score:.4f}")
        print(f"  Chunk ID: {rc.chunk.chunk_id}")
        print(f"  Doc Type: {rc.chunk.doc_type}")
        print(f"  Text Preview: {rc.chunk.text[:200]}...")
    
    print(f"\nTotal retrieved: {len(retrieved)}")
    
    # Run full pipeline to see final answer
    result = pipeline.query(query)
    print(f"\nFinal Answer: {result.answer}")
    print(f"Final Sources: {[s['source'] for s in result.sources]}")
