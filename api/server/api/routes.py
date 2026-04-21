"""HTTP routes for the RAG gateway.

Only two endpoints:

* ``GET  /api/health`` — liveness + pipeline readiness + index count
* ``POST /api/query``  — run a question through the evaluated pipeline

The streaming endpoint was intentionally removed. The canonical pipeline
(`app.pipeline.Pipeline`) returns a fully-formed `PipelineResult`; there is
no native token stream to forward. A faked SSE layer would bypass the
pipeline's grounding gate and duplicate its policy checks, reintroducing
exactly the eval/product drift this module exists to eliminate.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from ..core.config import get_settings
from ..schemas import (
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from ..services.rag_service import PipelineNotReadyError, RagService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["rag"])


def _service(request: Request) -> RagService:
    service: RagService | None = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialised",
        )
    return service


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    service: RagService | None = getattr(request.app.state, "rag_service", None)

    if service is None:
        return HealthResponse(
            status="starting",
            pipeline_ready=False,
            version=settings.version,
            chat_model=settings.chat_model,
            detail="Service not mounted yet",
        )

    return HealthResponse(
        status="ok" if service.ready else "starting",
        pipeline_ready=service.ready,
        version=settings.version,
        chat_model=settings.chat_model,
        index_count=service.index_count,
        detail=None if service.ready else "Pipeline initialising",
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    settings = get_settings()
    service = _service(request)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    if len(question) > settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Question exceeds max length "
                f"({settings.max_question_length} chars)"
            ),
        )

    try:
        result = await service.query(question)
    except PipelineNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception(
            "Query failed",
            extra={
                "question_preview": question[:120],
                "question_length": len(question),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error while processing query",
        ) from exc

    return QueryResponse(
        answer=result["answer"],
        sources=result["sources"],
        latency_ms=result["latency_ms"],
    )
