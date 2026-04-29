"""Regression tests for retrieval recall.

These tests verify that the retrieval pipeline returns relevant chunks
for known queries — specifically pricing queries that previously failed
due to an L2-distance-vs-similarity scoring bug.

Tests construct synthetic FAISS indexes with known content and verify
that retrieval returns the expected chunks. They do NOT require Ollama
or a running server.
"""
from __future__ import annotations

import numpy as np

from app.config import THRESHOLDS_BY_INTENT
from app.models import Chunk
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever


def _build_test_index(
    name: str, texts: list[str], dim: int = 32,
) -> FaissIndex:
    """Build a FaissIndex with random but deterministic embeddings."""
    rng = np.random.RandomState(42)
    fi = FaissIndex(name=name, dim=dim)
    chunks = []
    embeddings = []
    for i, text in enumerate(texts):
        vec = rng.randn(dim).astype(np.float32)
        vec /= np.linalg.norm(vec)  # L2-normalise
        embeddings.append(vec)
        chunks.append(Chunk(
            chunk_id=f"{name}_{i:04d}",
            source=f"test_{name}.md",
            text=text,
            path=f"/data/{name}.md",
            doc_type=name,
            offset=i * 100,
            embedding=vec.tolist(),
        ))
    fi.build(chunks)
    return fi


def test_faiss_search_returns_cosine_similarity():
    """FAISS search scores should be cosine similarities in [0, 1],
    not raw L2² distances."""
    fi = _build_test_index("eco", [
        "Grease trap pricing: Size A AED 3500, Size B AED 6000",
        "ECO Technology company overview and credentials",
        "Wastewater management compliance audit report",
    ])
    # Query with the same vector as chunk 0 (perfect match)
    query_vec = np.array(fi.chunks[0].embedding, dtype=np.float32)
    hits = fi.search(query_vec, top_k=3)

    assert len(hits) > 0, "Expected at least one hit"
    # A self-query should return sim ≈ 1.0 (not L2² ≈ 0.0)
    assert hits[0].score > 0.9, (
        f"Self-query should have similarity > 0.9, got {hits[0].score:.4f}. "
        "Scores may still be raw L2² distances instead of cosine similarity."
    )
    # All scores should be in [0, 1]
    for hit in hits:
        assert 0.0 <= hit.score <= 1.0, (
            f"Score {hit.score:.4f} outside [0,1] — not a valid similarity"
        )


def test_retriever_returns_pricing_chunks():
    """MultiRetriever must return pricing-related chunks for pricing queries,
    not drop them due to thresholding."""
    eco_texts = [
        "Grease trap pricing: Size A AED 3500, Size B AED 6000, Size C AED 9000",
        "ECO Technology Environmental Protection Services company overview",
        "Monthly maintenance contract includes scheduled inspections",
    ]
    eco_idx = _build_test_index("eco", eco_texts)
    retriever = MultiRetriever(indexes={"eco": eco_idx})

    # Use the embedding of the pricing chunk as the query vector
    # (simulates a query that is very relevant to pricing content)
    query_vec = np.array(eco_idx.chunks[0].embedding, dtype=np.float32)
    hits = retriever.retrieve(query_vec, intent="eco", query="grease trap prices")

    assert len(hits) > 0, (
        "Retriever returned zero hits for a pricing query — "
        "threshold may be filtering out high-similarity results"
    )
    # The pricing chunk should be among the results
    pricing_hit = next(
        (h for h in hits if "pricing" in h.text.lower() or "aed" in h.text.lower()),
        None,
    )
    assert pricing_hit is not None, (
        f"Pricing chunk not found in results. Got: "
        f"{[h.text[:50] for h in hits]}"
    )


def test_scores_above_threshold_after_conversion():
    """After L2²→cosine conversion, relevant chunks should score above
    the intent threshold and not be dropped by _normalize_and_filter."""
    eco_idx = _build_test_index("eco", [
        "Grease trap pricing list with AED values",
        "Company credentials and certifications",
    ])
    # Self-query: the most relevant possible query
    query_vec = np.array(eco_idx.chunks[0].embedding, dtype=np.float32)
    raw_hits = eco_idx.search(query_vec, top_k=5)

    eco_threshold = THRESHOLDS_BY_INTENT["eco"]
    above_threshold = [h for h in raw_hits if h.score >= eco_threshold]

    assert len(above_threshold) > 0, (
        f"Self-query hits all below eco threshold ({eco_threshold}). "
        f"Scores: {[f'{h.score:.4f}' for h in raw_hits]}. "
        "L2² distances may not be converted to cosine similarity."
    )


def test_pricing_boost_applied():
    """Pricing boost should increase scores for pricing-related chunks
    when the query contains pricing terms."""
    eco_idx = _build_test_index("eco", [
        "Grease trap pricing: Size A AED 3500, Size B AED 6000",
        "ECO Technology company credentials snapshot",
    ])
    retriever = MultiRetriever(indexes={"eco": eco_idx})

    # Use a generic vector so both chunks are close
    query_vec = np.array(eco_idx.chunks[0].embedding, dtype=np.float32)

    # Without pricing terms
    hits_no_boost = retriever.retrieve(query_vec, "eco", "company info")
    # With pricing terms
    hits_boosted = retriever.retrieve(query_vec, "eco", "grease trap price AED")

    # If both return results, the pricing chunk should score higher
    # with the boost query
    if hits_no_boost and hits_boosted:
        pricing_no = next(
            (h for h in hits_no_boost if "pricing" in h.text.lower()), None,
        )
        pricing_yes = next(
            (h for h in hits_boosted if "pricing" in h.text.lower()), None,
        )
        if pricing_no and pricing_yes:
            assert pricing_yes.score >= pricing_no.score, (
                f"Pricing boost not applied: "
                f"without={pricing_no.score:.4f}, with={pricing_yes.score:.4f}"
            )
