"""RAG Microservice - FastAPI wrapper for RAG pipeline."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from app.rag_pipeline import RagPipeline

logger = logging.getLogger(__name__)

# Request/Response models
class RAGRequest(BaseModel):
    query: str

class RAGResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    retrieval_time: float
    generation_time: float
    request_id: str | None = None
    intent: str | None = None
    intent_confidence: float | None = None
    intent_method: str | None = None

# Global pipeline instance
rag_pipeline: RagPipeline | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for RAG pipeline."""
    global rag_pipeline

    # Startup
    logger.info("Initializing RAG pipeline...")
    rag_pipeline = RagPipeline()
    rag_pipeline.build_index()
    rag_pipeline.warmup()
    logger.info("RAG pipeline ready")

    yield

    # Shutdown
    logger.info("Shutting down RAG pipeline...")
    if rag_pipeline:
        rag_pipeline.close()
    logger.info("RAG pipeline shutdown complete")

# FastAPI app
app = FastAPI(
    title="RAG Microservice",
    description="Retrieval-Augmented Generation API for ECO Technology",
    version="1.0.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pipeline_ready": rag_pipeline is not None and rag_pipeline._is_ready
    }

@app.post("/query", response_model=RAGResponse)
async def query_rag(request: RAGRequest):
    """Query the RAG pipeline."""
    if not rag_pipeline or not rag_pipeline._is_ready:
        raise HTTPException(status_code=503, detail="RAG pipeline not ready")

    try:
        response = rag_pipeline.query(request.query)
        return RAGResponse(
            answer=response.answer,
            sources=response.sources,
            retrieval_time=response.retrieval_time,
            generation_time=response.generation_time,
            request_id=response.request_id,
            intent=response.intent,
            intent_confidence=response.intent_confidence,
            intent_method=response.intent_method,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run server
    port = int(os.getenv("RAG_SERVICE_PORT", 8001))
    uvicorn.run(
        "rag_service:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
