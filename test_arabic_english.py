"""Test Arabic query with English output enforcement."""

from app.rag_pipeline import RagPipeline

pipeline = RagPipeline()
pipeline.build_index()

# Test Arabic query
result = pipeline.query('ما هي شركة إيكو؟')
print(f'Query: ما هي شركة إيكو؟')
print(f'Answer: {result.answer}')
print(f'Sources: {[s["source"] for s in result.sources]}')
print()

# Test English query
result2 = pipeline.query('What is Eco company?')
print(f'Query: What is Eco company?')
print(f'Answer: {result2.answer}')
print(f'Sources: {[s["source"] for s in result2.sources]}')

pipeline.close()
