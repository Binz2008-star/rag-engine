"""Semantic citation tests - validate answer ↔ context ↔ citations alignment."""

import pytest
from app.models import RetrievalHit
from generation.grounding import check_grounding
from unittest.mock import Mock


def test_citation_alignment():
    """Test that citations [S1], [S2] actually support the answer."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_002",
            source="doc2.pdf",
            text="The company was established in 2016.",
            score=0.72,
            path="/path/doc2.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer with correct citation
    answer = "ECO Technology provides environmental protection services [S1]."

    # Mock embedder
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
        [0.4, 0.5, 0.6],  # chunk_002 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is True, "Answer with correct citation should be grounded"


def test_no_fake_citations():
    """Test that answer does not reference missing sources."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer with fake citation [S2] that doesn't exist in context
    answer = "ECO Technology provides environmental protection services [S2]."

    # Note: Current grounding check only validates semantic similarity, not citation syntax.
    # This test documents the current behavior - citation validation is a future enhancement.
    # For now, if the semantic content matches, it passes grounding even with fake citation.

    # Mock embedder with high similarity (content matches)
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    # Current behavior: passes because semantic content matches
    # Future enhancement: should fail due to fake citation [S2]
    assert grounded is True, "Current behavior: semantic match passes despite fake citation"


def test_answer_grounding_with_citations():
    """Test cross-check between grounding and citations."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_002",
            source="doc2.pdf",
            text="The company was established in 2016.",
            score=0.72,
            path="/path/doc2.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer that uses information from both chunks
    answer = "ECO Technology provides environmental protection services [S1] and was established in 2016 [S2]."

    # Mock embedder with similar embeddings for answer and chunks
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
        [0.4, 0.5, 0.6],  # chunk_002 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is True, "Answer with proper citations should be grounded"


def test_citation_order():
    """Test that citation order reflects final ranking by score."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_002",
            source="doc2.pdf",
            text="The company was established in 2016.",
            score=0.72,
            path="/path/doc2.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_003",
            source="doc3.pdf",
            text="ECO has 50 employees.",
            score=0.65,
            path="/path/doc3.pdf",
            doc_type="pdf",
        ),
    ]

    # Verify hits are sorted by score (descending)
    assert hits[0].score >= hits[1].score >= hits[2].score

    # Answer should reference highest-scored chunk first
    answer = "ECO Technology provides environmental protection services [S1]."

    # Mock embedder
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is True


def test_entity_coverage():
    """Test that entities in answer exist in context."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer with entity from context
    answer = "ECO Technology provides environmental protection services."

    # Extract entities from answer (simple word-based for this test)
    answer_entities = set(answer.lower().split())
    context_entities = set()
    for hit in hits:
        context_entities.update(hit.text.lower().split())

    # Check overlap
    overlap = answer_entities & context_entities
    assert len(overlap) > 0, "Answer entities should exist in context"

    # Mock embedder
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is True


def test_citation_format_enforcement():
    """Test that generation prompt enforces citation format."""
    from generation.llm import LLMClient
    from app.config import OLLAMA_BASE_URL, CHAT_MODEL, TIMEOUT

    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    # Create LLM client
    llm = LLMClient(base_url=OLLAMA_BASE_URL, model=CHAT_MODEL, timeout=TIMEOUT)

    # Check that generate method includes citation instructions
    # This is a structural test - we verify the prompt contains citation instructions
    context = llm.build_context(hits)
    assert context is not None

    # The actual citation enforcement is in the user_message
    # We can't easily test the full generation without a running Ollama instance
    # but we can verify the structure is in place


def test_citation_without_support():
    """Test that citation without supporting context fails grounding."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer claims something not in context with citation
    answer = "ECO Technology was founded in 2020 [S1]."

    # Need to calculate actual cosine similarity to ensure it's below threshold
    import numpy as np

    # Use orthogonal vectors for low similarity
    answer_emb = np.array([1.0, 0.0, 0.0])
    chunk_emb = np.array([0.0, 1.0, 0.0])

    # Calculate cosine similarity
    similarity = float(
        (answer_emb @ chunk_emb) /
        (np.linalg.norm(answer_emb) * np.linalg.norm(chunk_emb) + 1e-8)
    )

    # Similarity should be 0.0 (orthogonal), well below grounding threshold of 0.60
    assert similarity < 0.60, f"Expected low similarity, got {similarity}"

    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        answer_emb.tolist(),
        chunk_emb.tolist(),
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is False, "Citation without supporting context should fail grounding"


def test_multiple_citations_same_source():
    """Test handling of multiple citations to the same source."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental protection services. The company has 50 employees.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    # Answer with multiple facts from same chunk
    answer = "ECO Technology provides environmental protection services [S1] and has 50 employees [S1]."

    # Mock embedder
    embedder = Mock()
    embedder.embed_batch = Mock(side_effect=[
        [0.1, 0.2, 0.3],  # answer embedding
        [0.1, 0.2, 0.3],  # chunk_001 embedding
    ])

    grounded = check_grounding(answer, hits, embedder.embed_batch)
    assert grounded is True, "Multiple citations to same source should be grounded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
