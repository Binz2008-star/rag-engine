from __future__ import annotations

from app.models import PipelineResult
from events.emitter import emit
from router.features import normalize_query


class InferenceService:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def handle_query(self, query: str, query_id: str) -> PipelineResult:
        normalized_query = normalize_query(query)
        emit(
            "query_received",
            {
                "query_id": query_id,
                "query": query,
                "normalized_query": normalized_query,
            },
        )

        result = self.pipeline.run(query=query, query_id=query_id)

        emit(
            "route_decision",
            {
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
            },
        )

        emit(
            "retrieval_result",
            {
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
                "retrieval": [
                    {
                        "doc_id": hit.chunk_id,
                        "score": hit.score,
                        "source": hit.source,
                        "path": hit.path,
                        "doc_type": hit.doc_type,
                    }
                    for hit in result.retrieval
                ],
            },
        )

        emit(
            "generation_result",
            {
                "query_id": result.query_id,
                "query": result.query,
                "normalized_query": result.normalized_query,
                "intent": result.intent,
                "confidence": result.confidence,
                "intent_method": result.intent_method,
                "retrieval": [
                    {
                        "doc_id": hit.chunk_id,
                        "score": hit.score,
                        "source": hit.source,
                    }
                    for hit in result.retrieval
                ],
                "answer": result.answer,
                "grounded": result.grounded,
                "latency_ms": result.latency_ms,
                "model_version": result.model_version,
                "retriever_version": result.retriever_version,
                "failure_type": result.failure_type,
            },
        )

        if result.failure_type:
            emit(
                "failure",
                {
                    "query_id": result.query_id,
                    "query": result.query,
                    "normalized_query": result.normalized_query,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "intent_method": result.intent_method,
                    "retrieval": [
                        {
                            "doc_id": hit.chunk_id,
                            "score": hit.score,
                            "source": hit.source,
                        }
                        for hit in result.retrieval
                    ],
                    "answer": result.answer,
                    "grounded": result.grounded,
                    "latency_ms": result.latency_ms,
                    "model_version": result.model_version,
                    "retriever_version": result.retriever_version,
                    "failure_type": result.failure_type,
                },
            )

        return result
