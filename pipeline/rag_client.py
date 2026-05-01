"""
RAG API Client - Interface to RAG microservice for Robin AI integration.
"""

import logging
import os
import time
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://localhost:8001")
RAG_TIMEOUT = 30.0

# RAG usage tracking
_rag_query_log: list[Dict[str, Any]] = []


class RAGClient:
    """Client for RAG microservice."""

    def __init__(self, base_url: str = RAG_SERVICE_URL, timeout: float = RAG_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def query(self, query_text: str, caller: str = "unknown") -> Dict[str, Any]:
        """
        Query the RAG system for an answer.

        Args:
            query_text: The question to ask the RAG system
            caller: Identifier for who is calling (e.g., "robin_ai_agent")

        Returns:
            Dict containing answer, sources, timing, and intent info
        """
        start_time = time.time()

        try:
            logger.info(f"[RAG] Query from {caller}: {query_text[:100]}...")

            response = self.client.post(
                f"{self.base_url}/query",
                json={"query": query_text},
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            elapsed = time.time() - start_time

            # Log successful query
            logger.info(
                f"[RAG] Success from {caller} | "
                f"time={elapsed:.3f}s | "
                f"intent={result.get('intent')} | "
                f"confidence={result.get('intent_confidence')} | "
                f"sources={len(result.get('sources', []))}"
            )

            # Track usage
            _rag_query_log.append({
                "timestamp": time.time(),
                "caller": caller,
                "query": query_text,
                "success": True,
                "elapsed": elapsed,
                "intent": result.get("intent"),
                "intent_confidence": result.get("intent_confidence"),
                "sources_count": len(result.get("sources", [])),
                "answer_length": len(result.get("answer", "")),
            })

            return result

        except httpx.HTTPError as e:
            elapsed = time.time() - start_time
            logger.error(f"[RAG] HTTP error from {caller}: {e} | time={elapsed:.3f}s")

            # Track failed query
            _rag_query_log.append({
                "timestamp": time.time(),
                "caller": caller,
                "query": query_text,
                "success": False,
                "elapsed": elapsed,
                "error": str(e),
            })

            return {
                "answer": "Insufficient data.",
                "sources": [],
                "retrieval_time": 0.0,
                "generation_time": 0.0,
                "error": str(e)
            }
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[RAG] Unexpected error from {caller}: {e} | time={elapsed:.3f}s")

            # Track failed query
            _rag_query_log.append({
                "timestamp": time.time(),
                "caller": caller,
                "query": query_text,
                "success": False,
                "elapsed": elapsed,
                "error": str(e),
            })

            return {
                "answer": "Insufficient data.",
                "sources": [],
                "retrieval_time": 0.0,
                "generation_time": 0.0,
                "error": str(e)
            }

    def health_check(self) -> bool:
        """Check if RAG service is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/health", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            return data.get("pipeline_ready", False)
        except Exception as e:
            logger.error(f"RAG health check failed: {e}")
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()


def get_rag_usage_stats() -> Dict[str, Any]:
    """Get RAG usage statistics."""
    if not _rag_query_log:
        return {"total_queries": 0, "successful": 0, "failed": 0}

    successful = sum(1 for log in _rag_query_log if log["success"])
    failed = len(_rag_query_log) - successful
    avg_time = sum(log["elapsed"] for log in _rag_query_log) / len(_rag_query_log)

    # Intent distribution
    intent_dist: Dict[str, int] = {}
    for log in _rag_query_log:
        if log.get("success") and log.get("intent"):
            intent = log["intent"]
            intent_dist[intent] = intent_dist.get(intent, 0) + 1

    # Caller distribution
    caller_dist: Dict[str, int] = {}
    for log in _rag_query_log:
        caller = log.get("caller", "unknown")
        caller_dist[caller] = caller_dist.get(caller, 0) + 1

    return {
        "total_queries": len(_rag_query_log),
        "successful": successful,
        "failed": failed,
        "success_rate": successful / len(_rag_query_log) if _rag_query_log else 0,
        "avg_response_time": avg_time,
        "intent_distribution": intent_dist,
        "caller_distribution": caller_dist,
    }


def clear_rag_usage_log():
    """Clear the RAG usage log (useful for testing or periodic reset)."""
    global _rag_query_log
    _rag_query_log = []
    logger.info("RAG usage log cleared")


# Singleton instance
_rag_client: Optional[RAGClient] = None


def get_rag_client() -> RAGClient:
    """Get or create the singleton RAG client."""
    global _rag_client
    if _rag_client is None:
        _rag_client = RAGClient()
    return _rag_client


def is_service_or_compliance_query(query: str) -> bool:
    """
    Determine if a query should be routed to RAG for service/compliance info.

    These are the types of questions that benefit from document retrieval:
    - Service details (waste management, grease trap, etc.)
    - Compliance questions (regulations, permits, certifications)
    - Company information (services offered, coverage areas)
    """
    query_lower = query.lower()

    service_keywords = [
        "service", "waste", "grease trap", "sewage", "jetting",
        "compliance", "regulation", "permit", "certification",
        "iso", "municipality", "approved", "environmental",
        "offer", "provide", "handle", "manage"
    ]

    return any(keyword in query_lower for keyword in service_keywords)
