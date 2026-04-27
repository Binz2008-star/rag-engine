from __future__ import annotations

from events.emitter import emit_event
from app.models import PipelineResult
from router.features import normalize_query


class InferenceService:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def handle_query(self, query: str, query_id: str) -> PipelineResult:
        emit_event({
            "event_type": "query_received",
            "query_id": query_id,
            "query": query,
            "normalized_query": normalize_query(query),
        })

        result = self.pipeline.run(query=query, query_id=query_id)

        emit_event({
            "event_type": "route_decision",
            "query_id": result.query_id,
            "query": result.query,
            "normalized_query": result.normalized_query,
            "intent": result.intent,
            "confidence": result.confidence,
            "intent_method": result.intent_method,
            "routing_decision": result.intent,
            "intent_confidence": result.confidence,
        })

        emit_event({
            "event_type": "retrieval_result",
            "query_id": result.query_id,
            "query": result.query,
            "normalized_query": result.normalized_query,
            "intent": result.intent,
            "confidence": result.confidence,
            "intent_method": result.intent_method,
            "top_k_used": len(result.retrieval),
            "context_size_chars": sum(len(h.text) for h in result.retrieval),
            "retrieval": [
                {
                    "doc_id": h.chunk_id,
                    "score": h.score,
                    "source": h.source,
                    "path": h.path,
                    "doc_type": h.doc_type,
                }
                for h in result.retrieval
            ],
        })

        emit_event({
            "event_type": "generation_result",
            "query_id": result.query_id,
            "query": result.query,
            "normalized_query": result.normalized_query,
            "intent": result.intent,
            "confidence": result.confidence,
            "intent_method": result.intent_method,
            "top_k_used": len(result.retrieval),
            "context_size_chars": sum(len(h.text) for h in result.retrieval),
            "retrieval": [
                {
                    "doc_id": h.chunk_id,
                    "score": h.score,
                    "source": h.source,
                }
                for h in result.retrieval
            ],
            "answer": result.answer,
            "latency_ms": result.latency_ms,
            "model_version": result.model_version,
            "retriever_version": result.retriever_version,
            "failure_type": result.failure_type,
        })

        if result.failure_type:
            failure_event = {
                "event_type": "failure",
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
                "top_k_used": len(result.retrieval),
                "context_size_chars": sum(len(h.text) for h in result.retrieval),
                "retrieval": [
                    {
                        "doc_id": h.chunk_id,
                        "score": h.score,
                        "source": h.source,
                    }
                    for h in result.retrieval
                ],
                "answer": result.answer,
                "latency_ms": result.latency_ms,
                "model_version": result.model_version,
                "retriever_version": result.retriever_version,
                "failure_type": result.failure_type,
            }
            if result.knowledge_gap:
                failure_event["knowledge_gap"] = {
                    "gap_type": result.knowledge_gap.gap_type,
                    "confidence_if_adversarial": result.knowledge_gap.confidence_if_adversarial,
                    "suggested_action": result.knowledge_gap.suggested_action,
                    "missing_documents": result.knowledge_gap.missing_documents,
                    "missing_confidence": result.knowledge_gap.missing_confidence,
                }
            emit_event(failure_event)
            emit_event({
                "event_type": "query_failed",
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
                "routing_decision": result.intent,
                "intent_confidence": result.confidence,
                "top_k_used": len(result.retrieval),
                "context_size_chars": sum(len(h.text) for h in result.retrieval),
                "failure_type": result.failure_type,
            })
        else:
            emit_event({
                "event_type": "query_completed",
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
                "routing_decision": result.intent,
                "intent_confidence": result.confidence,
                "top_k_used": len(result.retrieval),
                "context_size_chars": sum(len(h.text) for h in result.retrieval),
                "latency_ms": result.latency_ms,
                "model_version": result.model_version,
                "retriever_version": result.retriever_version,
            })

        return result
