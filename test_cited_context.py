"""Test cited context formatting with [S1], [S2] style."""

import pytest
from app.models import RetrievalHit
from app.pipeline import Pipeline
from unittest.mock import Mock


def test_build_cited_context_basic():
    """Test basic cited context formatting."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
            page=1,
            section="Introduction",
        ),
        RetrievalHit(
            chunk_id="chunk_002",
            source="doc2.pdf",
            text="The company was established in 2016.",
            score=0.72,
            path="/path/doc2.pdf",
            doc_type="pdf",
            page=2,
        ),
    ]

    # Create a minimal pipeline instance to test the method
    # Mock retriever with indexes dict for CorpusTopicMap
    mock_retriever = Mock()
    mock_retriever.indexes = {}

    pipeline = Pipeline(
        router=Mock(),
        embedder=Mock(),
        retriever=mock_retriever,
        llm=Mock(),
    )

    context = pipeline._build_cited_context(hits, max_chars=10000)

    # Check that citations are present
    assert "[S1:" in context
    assert "[S2:" in context

    # Check that source metadata is included
    assert "source=doc1.pdf" in context
    assert "source=doc2.pdf" in context

    # Check that scores are included
    assert "score=0.850" in context
    assert "score=0.720" in context

    # Check that page info is included when available
    assert "page=1" in context
    assert "page=2" in context

    # Check that section info is included when available
    assert "section=Introduction" in context


def test_build_cited_context_without_metadata():
    """Test cited context formatting without page/section metadata."""
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental services.",
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
    ]

    mock_retriever = Mock()
    mock_retriever.indexes = {}

    pipeline = Pipeline(
        router=Mock(),
        embedder=Mock(),
        retriever=mock_retriever,
        llm=Mock(),
    )

    context = pipeline._build_cited_context(hits, max_chars=10000)

    # Check that citations are present
    assert "[S1:" in context

    # Check that source metadata is included
    assert "source=doc1.pdf" in context

    # Check that page/section are not included (since they're None)
    assert "page=" not in context
    assert "section=" not in context


def test_build_cited_context_truncation():
    """Test that context is truncated at max_chars."""
    # Create multiple chunks to test truncation
    hits = [
        RetrievalHit(
            chunk_id="chunk_001",
            source="doc1.pdf",
            text="ECO Technology provides environmental services. " * 50,
            score=0.85,
            path="/path/doc1.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_002",
            source="doc2.pdf",
            text="The company was established in 2016. " * 50,
            score=0.72,
            path="/path/doc2.pdf",
            doc_type="pdf",
        ),
        RetrievalHit(
            chunk_id="chunk_003",
            source="doc3.pdf",
            text="Another chunk that should be truncated. " * 50,
            score=0.65,
            path="/path/doc3.pdf",
            doc_type="pdf",
        ),
    ]

    mock_retriever = Mock()
    mock_retriever.indexes = {}

    pipeline = Pipeline(
        router=Mock(),
        embedder=Mock(),
        retriever=mock_retriever,
        llm=Mock(),
    )

    # Set max_chars to allow first chunk but truncate second
    context = pipeline._build_cited_context(hits, max_chars=1000)

    # Check that first chunk is included
    assert "[S1:" in context
    # Second chunk should be truncated
    assert "[S2:" not in context

    # Check that context length is within limit
    assert len(context) <= 1000


def test_build_cited_context_empty_hits():
    """Test cited context with empty hits list."""
    hits = []

    mock_retriever = Mock()
    mock_retriever.indexes = {}

    pipeline = Pipeline(
        router=Mock(),
        embedder=Mock(),
        retriever=mock_retriever,
        llm=Mock(),
    )

    context = pipeline._build_cited_context(hits, max_chars=10000)

    # Should return empty string
    assert context == ""


def test_retrieval_hit_with_optional_fields():
    """Test RetrievalHit dataclass with optional page/section fields."""
    hit = RetrievalHit(
        chunk_id="chunk_001",
        source="doc1.pdf",
        text="ECO Technology provides environmental services.",
        score=0.85,
        path="/path/doc1.pdf",
        doc_type="pdf",
        page=1,
        section="Introduction",
    )

    assert hit.page == 1
    assert hit.section == "Introduction"


def test_retrieval_hit_without_optional_fields():
    """Test RetrievalHit dataclass without optional page/section fields."""
    hit = RetrievalHit(
        chunk_id="chunk_001",
        source="doc1.pdf",
        text="ECO Technology provides environmental services.",
        score=0.85,
        path="/path/doc1.pdf",
        doc_type="pdf",
    )

    assert hit.page is None
    assert hit.section is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
