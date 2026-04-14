"""Test Arabic normalization and retrieval (normalization only, no translation)."""

from app.rag_pipeline import RagPipeline

def test_arabic_query():
    """Test that Arabic queries are normalized and work correctly."""
    pipeline = RagPipeline()

    try:
        print("Building index...")
        pipeline.build_index()

        # Test Arabic query (will be normalized but NOT translated)
        arabic_query = "من هو روبن إدوان؟"
        print(f"\nArabic query: {arabic_query}")
        print("Note: Arabic text is normalized but NOT translated to English")

        result = pipeline.query(arabic_query)
        print(f"\nAnswer: {result.answer}")
        print(f"Sources: {[s['source'] for s in result.sources]}")
        print(f"Retrieval time: {result.retrieval_time:.2f}s")
        print(f"Generation time: {result.generation_time:.2f}s")

    finally:
        pipeline.close()

if __name__ == "__main__":
    test_arabic_query()
