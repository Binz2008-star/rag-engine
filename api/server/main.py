from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

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
from .services.agent_executor import AgentExecutor  # noqa: E402
from .services.execution_guard import ExecutionGuard  # noqa: E402
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
