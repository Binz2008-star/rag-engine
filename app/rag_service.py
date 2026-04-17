"""
RAG Service - Adapter layer for RagPipeline.

Provides a clean interface for agents to query the RAG system
without needing to know about pipeline internals.
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

from .rag_pipeline import RagPipeline

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Response from RAG service containing answer and metadata."""
    answer: str
    sources: List[str]
    retrieval_time: float
    generation_time: float
    total_time: float
    num_chunks: int
    is_refusal: bool = False


class RAGService:
    """Service adapter for RAG pipeline with singleton pattern."""

    _instance: Optional['RAGService'] = None
    _pipeline: Optional[RagPipeline] = None

    def __new__(cls) -> 'RAGService':
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the service (lazy loading of pipeline)."""
        if self._pipeline is None:
            logger.info("Initializing RAG pipeline...")
            self._pipeline = RagPipeline()
            logger.info("RAG pipeline ready")

    def query(self, question: str, max_context_length: Optional[int] = None) -> RAGResponse:
        """
        Query the RAG system with a question.

        Args:
            question: The question to answer
            max_context_length: Optional max context length override (not used in current implementation)

        Returns:
            RAGResponse with answer and metadata
        """
        if not question or not question.strip():
            raise ValueError("Question must be a non-empty string")

        start_time = time.perf_counter()

        # Use RagPipeline.query which handles both retrieval and generation
        pipeline_response = self._pipeline.query(question)
        total_time = time.perf_counter() - start_time

        # Extract data from pipeline response
        answer = pipeline_response.answer
        sources = pipeline_response.sources

        # Check if this is a refusal
        is_refusal = self._is_refusal_response(answer)

        # Note: RagPipeline doesn't provide separate timing, so we estimate
        # In a real implementation, we'd modify RagPipeline to expose timing data
        retrieval_time = total_time * 0.3  # Estimate: 30% retrieval
        generation_time = total_time * 0.7  # Estimate: 70% generation

        response = RAGResponse(
            answer=answer,
            sources=sources,
            retrieval_time=retrieval_time,
            generation_time=generation_time,
            total_time=total_time,
            num_chunks=len(sources),  # Using sources count as chunk proxy
            is_refusal=is_refusal
        )

        logger.debug(
            f"RAG query completed in {total_time:.2f}s "
            f"(retrieval: {retrieval_time:.2f}s, generation: {generation_time:.2f}s) "
            f"with {len(sources)} sources"
        )

        return response

    def _is_refusal_response(self, answer: str) -> bool:
        """Check if the answer is a refusal response."""
        refusal_indicators = [
            "insufficient data",
            "cannot answer",
            "don't have enough information",
            "not enough information",
            "unable to answer",
            "i don't know"
        ]

        answer_lower = answer.lower().strip()
        return any(indicator in answer_lower for indicator in refusal_indicators)

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics if available."""
        # This could be extended to return more detailed stats
        # from the pipeline if needed
        return {
            "status": "ready",
            "service_type": "RAGService"
        }

    def health_check(self) -> bool:
        """Check if the service is healthy."""
        try:
            # Simple health check - try a minimal query
            response = self._pipeline.query("test")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Convenience function for easy access
def get_rag_service() -> RAGService:
    """Get the singleton RAG service instance."""
    return RAGService()
