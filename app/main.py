from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from app.utils import new_query_id
from app.inference_service import InferenceService
from app.pipeline import Pipeline
from router.intent_router import IntentRouter
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever
from retrieval.reranker import Reranker
from generation.llm import LLMClient


class QueryRequest(BaseModel):
    query: str


def _load_indexes(model_dir: Path) -> dict[str, FaissIndex]:
    indexes: dict[str, FaissIndex] = {}
    for name in ("cv", "eco", "general"):
        try:
            indexes[name] = FaissIndex.load(name, out_dir=model_dir)
        except FileNotFoundError:
            continue
    return indexes


def create_app() -> FastAPI:
    app = FastAPI(title="RAG Intent System")

    router = IntentRouter.from_active_model()
    embedder = Embedder()
    indexes = _load_indexes(Path("models"))
    if not indexes:
        raise RuntimeError("No FAISS indexes found. Run scripts/build_indexes.py first.")

    retriever = MultiRetriever(indexes=indexes)
    reranker = Reranker(embed_fn=embedder.embed_batch)
    llm = LLMClient()
    pipeline = Pipeline(router=router, embedder=embedder, retriever=retriever, llm=llm, reranker=reranker)
    service = InferenceService(pipeline=pipeline)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "router_loaded": True,
            "indexes_loaded": sorted(indexes.keys()),
            "model_version": pipeline.model_version,
            "retriever_version": pipeline.retriever_version,
        }

    @app.post("/query")
    def query(req: QueryRequest):
        query_id = new_query_id()
        result = service.handle_query(req.query, query_id)
        response = {
            "query_id": result.query_id,
            "intent": result.intent,
            "confidence": result.confidence,
            "intent_method": result.intent_method,
            "answer": result.answer,
            "grounded": result.grounded,
            "failure_type": result.failure_type,
            "sources": [h.source for h in result.retrieval],
            "latency_ms": result.latency_ms,
        }
        if result.knowledge_gap:
            response["knowledge_gap"] = {
                "gap_type": result.knowledge_gap.gap_type,
                "confidence_if_adversarial": result.knowledge_gap.confidence_if_adversarial,
                "suggested_action": result.knowledge_gap.suggested_action,
                "missing_documents": result.knowledge_gap.missing_documents,
                "missing_confidence": result.knowledge_gap.missing_confidence,
            }
        return response

    return app


app = create_app()
