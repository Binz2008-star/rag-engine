"""
RAG Client for Webhook Server (Phase 2)
Thin client to RAG backend with full graceful degradation.
"""
import logging
import os
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

RAG_BASE_URL = os.environ.get("RAG_BASE_URL", "http://localhost:8001")
RAG_TIMEOUT = 5.0  # Never block, 5 second max


class RAGClientWebhook:
    """
    Client for RAG backend with automatic graceful degradation.
    Never raises exceptions - returns safe defaults on any error.
    """

    def __init__(self, base_url: str = RAG_BASE_URL, timeout: float = RAG_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def classify_lead(self, question: str) -> Dict[str, Any]:
        """
        Classify lead intent via /api/dispatch.
        Returns: {intent, confidence, method, capability}
        """
        try:
            response = self._client.post(
                f"{self.base_url}/api/dispatch",
                json={"question": question},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return {
                "intent": data.get("kind", "general"),
                "confidence": data.get("payload", {}).get("confidence", 0.0),
                "method": data.get("payload", {}).get("method", "fallback"),
                "capability": data.get("capability", "chat"),
                "success": True,
            }
        except Exception as e:
            logger.warning(f"RAG classify_lead failed: {e}")
            return {
                "intent": "general",
                "confidence": 0.0,
                "method": "fallback",
                "capability": "chat",
                "success": False,
            }

    def generate_proposal_context(self, question: str) -> Dict[str, Any]:
        """
        Get RAG-grounded context for proposals via /api/query.
        For HOT/WARM leads - provides relevant company info.
        """
        try:
            response = self._client.post(
                f"{self.base_url}/api/query",
                json={"question": question},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if data.get("error"):
                return {
                    "context": "",
                    "grounded": False,
                    "error": data.get("detail", "RAG error"),
                }

            return {
                "context": data.get("answer", ""),
                "grounded": data.get("grounded", False),
                "sources": data.get("sources", []),
                "intent": data.get("intent", ""),
                "confidence": data.get("intent_confidence", 0.0),
            }
        except Exception as e:
            logger.warning(f"RAG generate_proposal_context failed: {e}")
            return {
                "context": "",
                "grounded": False,
                "error": str(e),
            }

    def forward_to_jotform_agent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Index lead into RAG memory via /api/webhooks/jotform-agent.
        """
        try:
            response = self._client.post(
                f"{self.base_url}/api/webhooks/jotform-agent",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"RAG forward_to_jotform_agent failed: {e}")
            return {"indexed": False, "error": str(e)}

    def rag_health(self) -> Dict[str, Any]:
        """
        Check RAG backend health via /api/health.
        """
        try:
            response = self._client.get(
                f"{self.base_url}/api/health",
                timeout=2.0
            )
            response.raise_for_status()
            data = response.json()
            return {
                "healthy": True,
                "pipeline_ready": data.get("pipeline_ready", False),
                "version": data.get("version", "unknown"),
            }
        except Exception as e:
            logger.warning(f"RAG health check failed: {e}")
            return {
                "healthy": False,
                "pipeline_ready": False,
                "error": str(e),
            }

    def close(self):
        """Close HTTP client."""
        self._client.close()


# Singleton
_rag_client: Optional[RAGClientWebhook] = None


def get_rag_client() -> RAGClientWebhook:
    """Get singleton RAG client."""
    global _rag_client
    if _rag_client is None:
        _rag_client = RAGClientWebhook()
    return _rag_client


def classify_lead(question: str) -> Dict[str, Any]:
    """Classify lead using RAG backend."""
    return get_rag_client().classify_lead(question)


def generate_proposal_context(question: str) -> Dict[str, Any]:
    """Get proposal context from RAG."""
    return get_rag_client().generate_proposal_context(question)


def forward_to_jotform_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward to RAG memory."""
    return get_rag_client().forward_to_jotform_agent(payload)


def rag_health() -> Dict[str, Any]:
    """Check RAG health."""
    return get_rag_client().rag_health()
