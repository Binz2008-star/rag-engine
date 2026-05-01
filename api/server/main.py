from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from json import JSONDecodeError
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from .admin_routes import register_admin_routes  # noqa: E402
from .whatsapp_routes import register_whatsapp_routes  # noqa: E402
from .jotform_routes import register_jotform_routes  # noqa: E402
from .core.config import get_settings  # noqa: E402
from .core.logging import configure_logging  # noqa: E402
from .infra.ollama_health import OllamaUnavailableError, check_ollama  # noqa: E402
from .schemas import (
    DispatchRequest,
    DispatchResponse,
    HealthResponse,
    JotformWebhookResponse,
    QueryRequest,
    QueryResponse,
)  # noqa: E402
from .services.agent_executor import AgentExecutor  # noqa: E402
from .services.execution_guard import ExecutionGuard  # noqa: E402
from .services.jotform_ingest_service import ingest_jotform_payload  # noqa: E402
from .services.rag_service import RagService  # noqa: E402
from .services.scheduler_service import SchedulerService  # noqa: E402
from .services.scheduler_worker import SchedulerWorker  # noqa: E402
from .services.task_store import TaskStore  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "Starting %s v%s on %s:%d",
        settings.app_name,
        settings.version,
        settings.host,
        settings.port,
    )

    # Initialize infrastructure services
    app.state.task_store = TaskStore()
    app.state.execution_guard = ExecutionGuard(app.state.task_store)
    app.state.scheduler_service = SchedulerService()
    app.state.agent_executor = AgentExecutor()

    app.state.rag_service = None

    # Start RAG service in background without blocking server startup
    async def init_rag_service():
        try:
            await check_ollama(
                base_url=settings.ollama_base_url,
                required_models=settings.ollama_required_models,
            )
            logger.info("Ollama health check passed")
        except OllamaUnavailableError as exc:
            logger.error("Ollama health check failed: %s - RAG features will be degraded", exc)
            return

        try:
            service = RagService(index_dir=settings.index_dir)
            app.state.rag_service = service
            await service.startup()
            logger.info("RAG service startup completed")
        except Exception:
            logger.exception("RAG service startup failed - API will report degraded")
            app.state.rag_service = None

    # Schedule RAG initialization as background task
    import asyncio
    app.state.rag_init_task = asyncio.create_task(init_rag_service())

    # Initialize scheduler worker (but don't start yet)
    app.state.scheduler_worker = SchedulerWorker(
        task_store=app.state.task_store,
        scheduler_service=app.state.scheduler_service,
        execution_guard=app.state.execution_guard,
        agent_executor=app.state.agent_executor,
    )

    # Store scheduler task reference for shutdown
    app.state.scheduler_task = None
    app.state.scheduler_startup_task = None

    # Wait for RAG initialization before starting scheduler
    async def start_scheduler_after_rag():
        try:
            # Wait for RAG init to complete (or fail gracefully)
            await app.state.rag_init_task
            logger.info("RAG initialization complete, starting scheduler worker")
        except Exception:
            logger.warning("RAG initialization failed, starting scheduler worker in degraded mode")

        # Now start the scheduler worker
        async def run_scheduler_worker():
            try:
                await asyncio.to_thread(app.state.scheduler_worker.run_forever)
            except asyncio.CancelledError:
                logger.info("Scheduler worker cancelled during shutdown")
            except Exception:
                logger.exception("Scheduler worker failed unexpectedly")

        app.state.scheduler_task = asyncio.create_task(run_scheduler_worker())

    app.state.scheduler_startup_task = asyncio.create_task(start_scheduler_after_rag())

    try:
        yield
    finally:
        # Shutdown scheduler worker cooperatively
        logger.info("Shutting down scheduler worker")
        if app.state.scheduler_worker is not None:
            app.state.scheduler_worker.stop()
        if app.state.scheduler_startup_task is not None and not app.state.scheduler_startup_task.done():
            app.state.scheduler_startup_task.cancel()
            try:
                await app.state.scheduler_startup_task
            except asyncio.CancelledError:
                pass
        if app.state.scheduler_task is not None:
            app.state.scheduler_task.cancel()
            try:
                await app.state.scheduler_task
            except asyncio.CancelledError:
                pass

        # Shutdown RAG service
        if app.state.rag_service is not None:
            logger.info("Shutting down RAG service")
            await app.state.rag_service.shutdown()

        # Cancel RAG init task if still running
        if app.state.rag_init_task is not None and not app.state.rag_init_task.done():
            logger.info("Cancelling RAG initialization task")
            app.state.rag_init_task.cancel()
            try:
                await app.state.rag_init_task
            except asyncio.CancelledError:
                pass


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.version,
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "3.0"}

    @app.get("/leads/hot")
    async def get_hot_leads() -> dict[str, Any]:
        """Return hot leads for sales follow-up."""
        return {"leads": [], "count": 0}

    @app.get("/api/health")
    async def api_health() -> HealthResponse:
        rag_service: RagService | None = getattr(app.state, "rag_service", None)
        return HealthResponse(
            status="ok",
            pipeline_ready=rag_service.ready if rag_service else False,
            version=settings.version,
            chat_model=settings.chat_model,
            index_count=rag_service.index_count if rag_service else None,
        )

    @app.post("/api/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse | JSONResponse:
        """Execute a RAG query against the knowledge base."""
        rag_service: RagService | None = getattr(app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "RAG service not ready", "detail": "Pipeline is initializing or unavailable"},
            )
        try:
            result = await rag_service.query(request.question)
            return QueryResponse(**result)
        except Exception as e:
            logger.exception("Query failed")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Query failed", "detail": str(e)},
            )

    @app.post("/api/leads/score")
    async def score_lead(request: Request) -> JSONResponse:
        """Score a lead using LeadScorer (same as backfill and webhook)."""
        from lead_scorer import get_scorer

        try:
            data = await request.json()
        except JSONDecodeError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid JSON"},
            )

        # Map API fields to LeadScorer expected format
        lead_data = {
            "services_required": data.get("services", []),
            "company_name": data.get("company_name", data.get("company", "")),
            "location": data.get("location", data.get("emirate", "")),
            "source": data.get("source", "api"),
            "message": data.get("message", ""),
            "notes": data.get("notes", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "full_name": data.get("full_name", data.get("name", "")),
        }

        # Build RAG result from intent/urgency if provided
        rag_result = None
        if data.get("intent"):
            rag_result = {
                "intent": data.get("intent"),
                "confidence": 0.9 if data.get("intent") in ["eco", "quote", "consultation"] else 0.7,
                "method": "api_direct",
            }

        # Score using same LeadScorer as backfill and webhook
        scorer = get_scorer()
        result = scorer.score(lead_data, rag_result)

        return JSONResponse(
            content={
                "score": result["lead_score"],
                "band": result["score_band"],
                "recommended_action": result["recommended_action"],
                "breakdown": result.get("scores", {}),
                "weighted": result.get("weighted_scores", {}),
                "version": "2.0-leadscorer",
            }
        )

    @app.post("/api/dispatch", response_model=DispatchResponse)
    async def dispatch(request: DispatchRequest) -> DispatchResponse:
        """Route a question to the appropriate capability."""
        from router.intent_router import IntentRouter

        router = IntentRouter.from_active_model()
        route_result = router.route(request.question)

        # Map intent to capability
        capability_map = {
            "cv": "cv",
            "eco": "eco",
            "general": "chat",
        }
        capability = capability_map.get(route_result.intent, "chat")

        return DispatchResponse(
            capability=capability,
            kind=route_result.intent,
            status="ok",
            request_id=str(uuid.uuid4()),
            payload={
                "intent": route_result.intent,
                "confidence": route_result.confidence,
                "method": route_result.intent_method,
                "question": request.question,
            },
        )

    @app.post("/api/webhooks/jotform-agent")
    async def jotform_webhook(request: Request) -> JSONResponse:
        """Ingest Jotform AI Agent webhook payload as structured lead + RAG memory."""
        request_id = str(uuid.uuid4())

        # 1. AuthN first — reject unauthenticated callers BEFORE we do any
        #    body parsing, size checks, or JSON deserialization. This prevents
        #    unauth'd requests from triggering parser work or 413 responses.
        if settings.jotform_webhook_secret:
            provided_secret = request.headers.get("X-Jotform-Secret")
            if provided_secret != settings.jotform_webhook_secret:
                logger.warning(
                    "Jotform webhook secret validation failed (request_id=%s)",
                    request_id,
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"error": "Invalid webhook secret"},
                )

        # 2. Feature flag — also before parsing.
        if not settings.jotform_webhook_enabled:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Jotform webhook is disabled"},
            )

        # 3. Parse JSON only after auth + enabled checks pass.
        try:
            payload = await request.json()
        except JSONDecodeError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid JSON payload"},
            )

        if not payload or not isinstance(payload, dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Payload must be a non-empty object"},
            )

        # Payload size guard (100KB limit)
        import json
        try:
            payload_size = len(json.dumps(payload))
            if payload_size > 100_000:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"error": "Payload too large (max 100KB)"},
                )
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid payload structure"},
            )

        # Ingest payload in thread pool to avoid blocking
        try:
            lead = await asyncio.to_thread(ingest_jotform_payload, payload)
            logger.info("Jotform lead ingested successfully (request_id=%s, lead_id=%s, intent=%s)", request_id, lead.lead_id, lead.intent)
            response = JotformWebhookResponse(
                status="ok",
                source="jotform",
                lead_id=lead.lead_id,
                intent=lead.intent,
                indexed=False,  # File-based storage, requires index rebuild
                request_id=request_id,
            )
            return JSONResponse(content=response.model_dump(), status_code=status.HTTP_200_OK)
        except ValueError as e:
            logger.error("Jotform webhook validation error (request_id=%s): %s", request_id, e)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": str(e)},
            )
        except Exception as e:
            logger.exception("Jotform webhook ingestion failed (request_id=%s): %s", request_id, e)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Ingestion failed"},
            )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "ValidationError", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "detail": "Unexpected error"},
        )

    register_admin_routes(app)
    register_whatsapp_routes(app)
    register_jotform_routes(app)

    return app


app = create_app()
