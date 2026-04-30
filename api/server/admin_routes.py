"""Admin API routes.

Adds the following endpoints consumed by the admin dashboard:

- GET  /api/health     -- lightweight health probe
- GET  /admin/stats    -- system-wide statistics + monitoring
- GET  /leads          -- all leads (most recent first)
- GET  /leads/hot      -- hot leads only
- GET  /leads/failures -- queries that hit retrieval_miss or other failures
- GET  /leads/flagged  -- manually flagged bad answers
- POST /leads/{id}/flag -- toggle flag on a lead
- POST /leads/{id}/rerun -- re-dispatch a lead's query
- GET  /admin/monitoring -- aggregate latency / failure stats
- POST /api/dispatch   -- forward a query through the RAG pipeline
- POST /api/dashboard/eval-cases -- save an eval case (JSONL)
- GET  /api/dashboard/eval-cases -- list recent eval cases
- GET  /api/dashboard/rag-config  -- read RAG runtime config
- POST /api/dashboard/rag-config  -- update RAG runtime config
"""

from __future__ import annotations

from filelock import FileLock
import json
import logging
import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from .services.leads_store import get_leads_store
from .services.rag_config import get_config_version

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _generate_default_token() -> str:
    """Return a random token when none is configured (dev convenience)."""
    token = secrets.token_urlsafe(32)
    logger.warning(
        "No ADMIN_TOKEN configured -- generated ephemeral token: %s", token
    )
    return token


if not ADMIN_TOKEN:
    ADMIN_TOKEN = _generate_default_token()


async def verify_admin_token(
    x_admin_token: str = Header(default=""),
) -> None:
    """Dependency that rejects requests missing a valid admin token.

    The dashboard page itself injects the token from the login form into
    every fetch() call via the ``X-Admin-Token`` header.
    """
    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


# ---------------------------------------------------------------------------
# Lead temperature classification
# ---------------------------------------------------------------------------

_HOT_INTENTS = {"eco", "cv"}
_WARM_CONFIDENCE_THRESHOLD = 0.65


def classify_lead_temperature(intent: str, confidence: float) -> str:
    """Derive hot / warm / cold from intent + confidence."""
    if intent in _HOT_INTENTS and confidence >= _WARM_CONFIDENCE_THRESHOLD:
        return "hot"
    if confidence >= _WARM_CONFIDENCE_THRESHOLD:
        return "warm"
    return "cold"


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_admin_routes(app: FastAPI) -> None:
    """Attach admin endpoints to *app*."""

    from pathlib import Path
    _STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

    # ---- Dashboard page (HTML) -----------------------------------------

    @app.get("/admin", include_in_schema=False)
    async def admin_page() -> HTMLResponse:
        html_path = _STATIC_DIR / "admin.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    # ---- API health (lightweight) --------------------------------------

    @app.get("/api/health")
    async def api_health(request: Request) -> Dict[str, Any]:
        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count
        return {
            "status": "ok",
            "rag_ready": rag_ready,
            "index_count": index_count,
            "timestamp": time.time(),
        }

    # ---- System health (used by the original /health) ------------------

    @app.get("/health")
    async def health_check(request: Request) -> Dict[str, Any]:
        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count
        from .core.config import get_settings
        settings = get_settings()
        return {
            "status": "ok",
            "pipeline_ready": rag_ready,
            "version": settings.version,
            "chat_model": settings.chat_model,
            "index_count": index_count,
        }

    # ---- Admin stats (protected) ---------------------------------------

    @app.get("/admin/stats", dependencies=[Depends(verify_admin_token)])
    async def admin_stats(request: Request) -> Dict[str, Any]:
        store = get_leads_store()
        counts = store.counts_by_temperature()
        total = store.total_count()

        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count

        from .core.config import get_settings
        settings = get_settings()

        monitoring = store.monitoring_stats()

        return {
            "system": {
                "status": "ok",
                "version": settings.version,
                "chat_model": settings.chat_model,
                "rag_ready": rag_ready,
                "index_count": index_count,
            },
            "leads": {
                "total": total,
                "hot": counts.get("hot", 0),
                "warm": counts.get("warm", 0),
                "cold": counts.get("cold", 0),
            },
            "monitoring": monitoring,
        }

    # ---- Monitoring (protected) ----------------------------------------

    @app.get("/admin/monitoring", dependencies=[Depends(verify_admin_token)])
    async def admin_monitoring() -> Dict[str, Any]:
        store = get_leads_store()
        return store.monitoring_stats()

    # ---- Leads (protected) ---------------------------------------------

    @app.get("/leads", dependencies=[Depends(verify_admin_token)])
    async def list_leads() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_all(limit=200)
        return {"leads": leads, "total": store.total_count()}

    @app.get("/leads/hot", dependencies=[Depends(verify_admin_token)])
    async def list_hot_leads() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_by_temperature("hot", limit=200)
        return {"leads": leads, "total": len(leads)}

    @app.get("/leads/failures", dependencies=[Depends(verify_admin_token)])
    async def list_failures() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_failures(limit=200)
        return {"leads": leads, "total": len(leads)}

    @app.get("/leads/flagged", dependencies=[Depends(verify_admin_token)])
    async def list_flagged() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_flagged(limit=200)
        return {"leads": leads, "total": len(leads)}

    # ---- Lead actions (protected) --------------------------------------

    @app.post("/leads/{lead_id}/flag", dependencies=[Depends(verify_admin_token)])
    async def toggle_flag(lead_id: int) -> Dict[str, Any]:
        store = get_leads_store()
        lead = store.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        new_state = not bool(lead.get("flagged", 0))
        store.flag(lead_id, flagged=new_state)
        return {"id": lead_id, "flagged": new_state}

    @app.post("/leads/{lead_id}/rerun", dependencies=[Depends(verify_admin_token)])
    async def rerun_query(lead_id: int, request: Request) -> Dict[str, Any]:
        store = get_leads_store()
        lead = store.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            raise HTTPException(
                status_code=503, detail="RAG pipeline not ready"
            )

        question = lead["query"]
        t0 = time.perf_counter()
        result = await rag_service.query(question)
        wall_ms = int((time.perf_counter() - t0) * 1000)

        intent = result.get("intent", "general")
        confidence = result.get("intent_confidence", 0.0)
        temperature = classify_lead_temperature(intent, confidence)
        failure_type = result.get("failure_type")
        answer = result.get("answer", "")

        new_id = store.capture(
            query=question,
            intent=intent,
            temperature=temperature,
            source="admin_rerun",
            channel="api",
            latency_ms=wall_ms,
            failure_type=failure_type,
            answer=answer,
            metadata={"dispatch_result": result, "rerun_of": lead_id},
        )

        return {
            "original_id": lead_id,
            "new_id": new_id,
            "capability": "rag",
            "kind": intent,
            "status": "ok",
            "payload": result,
        }

    # ---- Dispatch (protected) ------------------------------------------

    @app.post("/api/dispatch", dependencies=[Depends(verify_admin_token)])
    async def dispatch_query(request: Request) -> Dict[str, Any]:
        body = await request.json()
        question = (body.get("question") or body.get("query") or "").strip()
        if not question:
            raise HTTPException(status_code=422, detail="question is required")

        session_id = body.get("session_id")
        user_id = body.get("user_id")

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            raise HTTPException(
                status_code=503, detail="RAG pipeline not ready"
            )

        t0 = time.perf_counter()
        result = await rag_service.query(question)
        wall_ms = int((time.perf_counter() - t0) * 1000)

        intent = result.get("intent", "general")
        confidence = result.get("intent_confidence", 0.0)
        temperature = classify_lead_temperature(intent, confidence)
        failure_type = result.get("failure_type")
        answer = result.get("answer", "")

        store = get_leads_store()
        store.capture(
            query=question,
            intent=intent,
            temperature=temperature,
            source="admin_dispatch",
            session_id=session_id,
            user_id=user_id,
            channel="api",
            latency_ms=wall_ms,
            failure_type=failure_type,
            answer=answer,
            metadata={"dispatch_result": result},
        )

        return {
            "capability": "rag",
            "kind": intent,
            "status": "ok",
            "request_id": result.get("request_id", ""),
            "config_version": get_config_version(),
            "payload": result,
        }

    # ---- Eval cases (protected) ----------------------------------------

    _EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "data"
    _EVAL_FILE = _EVAL_DIR / "eval_cases.jsonl"

    _VALID_FEEDBACK_LABELS = {
        "good", "bad", "wrong_source", "too_slow", "false_refusal",
    }

    def _locked_jsonl_append(path: Path, data: Dict[str, Any]) -> None:
        """Append one JSON line with cross-platform file locking."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = str(path) + ".lock"
        lock = FileLock(lock_path)
        with lock:
            with open(path, "a", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
                f.write("\n")

    @app.post(
        "/api/dashboard/eval-cases",
        dependencies=[Depends(verify_admin_token)],
    )
    async def save_eval_case(request: Request) -> Dict[str, Any]:
        body = await request.json()

        query = (body.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=422, detail="query is required")

        feedback_label = (body.get("feedback_label") or "").strip().lower()
        if not feedback_label:
            raise HTTPException(
                status_code=422, detail="feedback_label is required"
            )
        if feedback_label not in _VALID_FEEDBACK_LABELS:
            raise HTTPException(
                status_code=422,
                detail=f"feedback_label must be one of: {', '.join(sorted(_VALID_FEEDBACK_LABELS))}",
            )

        must_include = body.get("must_include", [])
        if isinstance(must_include, str):
            must_include = [s.strip() for s in must_include.split(",") if s.strip()]

        case: Dict[str, Any] = {
            "query": query,
            "actual_answer": body.get("actual_answer"),
            "expected_intent": body.get("expected_intent"),
            "expected_source": body.get("expected_source"),
            "must_include": must_include,
            "feedback_label": feedback_label,
            "notes": body.get("notes"),
            "actual_intent": body.get("actual_intent"),
            "actual_failure_type": body.get("actual_failure_type"),
            "actual_sources": body.get("actual_sources"),
            "latency_ms": body.get("latency_ms"),
            "request_id": body.get("request_id"),
            "config_version": get_config_version(),
            "created_at": time.time(),
        }

        _locked_jsonl_append(_EVAL_FILE, case)

        logger.info("eval_case: saved query=%r label=%s", query[:60], feedback_label)
        return {"status": "ok", "saved": True}

    @app.get(
        "/api/dashboard/eval-cases",
        dependencies=[Depends(verify_admin_token)],
    )
    async def list_eval_cases() -> Dict[str, Any]:
        if not _EVAL_FILE.exists():
            return {"cases": [], "total": 0}

        cases: List[Dict[str, Any]] = []
        for line in _EVAL_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        cases.reverse()
        return {"cases": cases, "total": len(cases)}

    # ---- RAG runtime config (protected) --------------------------------

    _CONFIG_FILE = _EVAL_DIR / "rag_runtime_config.json"

    _DEFAULT_RAG_CONFIG: Dict[str, Any] = {
        "top_k": 15,
        "score_threshold": 0.38,
        "max_context_chars": 3000,
        "temperature": 0.2,
        "reranker_enabled": True,
        "grounding_strictness": 0.5,
        "version": 1,
        "updated_at": None,
        "updated_by": None,
        "notes": "",
    }

    def _load_rag_config() -> Dict[str, Any]:
        """Load config from disk, returning defaults if missing."""
        if not _CONFIG_FILE.exists():
            return dict(_DEFAULT_RAG_CONFIG)
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            merged = dict(_DEFAULT_RAG_CONFIG)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("rag_config: failed to load %s: %s", _CONFIG_FILE, exc)
            return dict(_DEFAULT_RAG_CONFIG)

    def _save_rag_config(config: Dict[str, Any]) -> None:
        """Atomically write config to disk via tmp+rename."""
        _EVAL_DIR.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(_EVAL_DIR), suffix=".tmp", prefix="rag_config_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(config, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp_path, str(_CONFIG_FILE))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    _RAG_CONFIG_KEYS = {
        "top_k", "score_threshold", "max_context_chars",
        "temperature", "reranker_enabled", "grounding_strictness",
        "notes",
    }

    @app.get(
        "/api/dashboard/rag-config",
        dependencies=[Depends(verify_admin_token)],
    )
    async def get_rag_config() -> Dict[str, Any]:
        config = _load_rag_config()
        return {"config": config}

    @app.post(
        "/api/dashboard/rag-config",
        dependencies=[Depends(verify_admin_token)],
    )
    async def update_rag_config(request: Request) -> Dict[str, Any]:
        body = await request.json()

        current = _load_rag_config()

        for key in _RAG_CONFIG_KEYS:
            if key in body:
                current[key] = body[key]

        if not isinstance(current["top_k"], int) or current["top_k"] < 1:
            raise HTTPException(status_code=422, detail="top_k must be a positive integer")
        if not isinstance(current["score_threshold"], (int, float)):
            raise HTTPException(status_code=422, detail="score_threshold must be a number")
        if not isinstance(current["max_context_chars"], int) or current["max_context_chars"] < 100:
            raise HTTPException(status_code=422, detail="max_context_chars must be >= 100")
        if not isinstance(current["temperature"], (int, float)):
            raise HTTPException(status_code=422, detail="temperature must be a number")
        if not isinstance(current["reranker_enabled"], bool):
            raise HTTPException(status_code=422, detail="reranker_enabled must be a boolean")
        if not isinstance(current["grounding_strictness"], (int, float)):
            raise HTTPException(status_code=422, detail="grounding_strictness must be a number")

        current["version"] = current.get("version", 0) + 1
        current["updated_at"] = time.time()
        current["updated_by"] = body.get("updated_by", "admin")

        _save_rag_config(current)

        logger.info(
            "rag_config: updated v%d by %s",
            current["version"],
            current["updated_by"],
        )
        return {"status": "ok", "config": current}

    # ---- Operator Console (Issue #34) ------------------------------------

    _RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
    _MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"

    @app.get("/admin/operator", include_in_schema=False)
    async def operator_page() -> HTMLResponse:
        """Operator Console HTML page."""
        html_path = _STATIC_DIR / "operator.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Operator Console not found")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @app.post("/admin/ask", dependencies=[Depends(verify_admin_token)])
    async def operator_ask(request: Request) -> Dict[str, Any]:
        """Ask the RAG system a question (Operator Console)."""
        body = await request.json()
        question = (body.get("question") or body.get("query") or "").strip()
        if not question:
            raise HTTPException(status_code=422, detail="question is required")

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            raise HTTPException(status_code=503, detail="RAG pipeline not ready")

        t0 = time.perf_counter()
        result = await rag_service.query(question)
        wall_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "status": "ok",
            "query": question,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "intent": result.get("intent", "general"),
            "intent_confidence": result.get("intent_confidence", 0.0),
            "grounded": result.get("grounded", False),
            "failure_type": result.get("failure_type"),
            "latency_ms": wall_ms,
            "request_id": result.get("request_id", ""),
        }

    @app.get("/admin/knowledge", dependencies=[Depends(verify_admin_token)])
    async def list_knowledge_files() -> Dict[str, Any]:
        """List all knowledge files in data/raw."""
        _RAW_DIR.mkdir(parents=True, exist_ok=True)
        files = []
        for path in sorted(_RAW_DIR.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
                rel_path = path.relative_to(_RAW_DIR)
                files.append({
                    "name": str(rel_path).replace("\\", "/"),
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                })
        return {"files": files, "total": len(files)}

    @app.get("/admin/knowledge/{filename:path}", dependencies=[Depends(verify_admin_token)])
    async def get_knowledge_file(filename: str) -> Dict[str, Any]:
        """Read a knowledge file."""
        # Prevent path traversal
        safe_name = filename.replace("..", "").replace("//", "/").lstrip("/")
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid filename")

        file_path = _RAW_DIR / safe_name
        try:
            file_path.relative_to(_RAW_DIR)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        suffix = file_path.suffix.lower()
        if suffix not in {".txt", ".md"}:
            raise HTTPException(status_code=400, detail="Only .txt and .md files allowed")

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return {
            "filename": safe_name,
            "content": content,
            "size": len(content),
            "modified": file_path.stat().st_mtime,
        }

    @app.post("/admin/knowledge/{filename:path}", dependencies=[Depends(verify_admin_token)])
    async def save_knowledge_file(filename: str, request: Request) -> Dict[str, Any]:
        """Save a knowledge file."""
        body = await request.json()
        content = body.get("content", "")

        # Prevent path traversal
        safe_name = filename.replace("..", "").replace("//", "/").lstrip("/")
        if not safe_name:
            raise HTTPException(status_code=400, detail="Invalid filename")

        file_path = _RAW_DIR / safe_name
        try:
            file_path.relative_to(_RAW_DIR)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path")

        suffix = file_path.suffix.lower()
        if suffix not in {".txt", ".md"}:
            raise HTTPException(status_code=400, detail="Only .txt and .md files allowed")

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")
        return {
            "status": "ok",
            "filename": safe_name,
            "size": len(content),
            "saved_at": time.time(),
        }

    @app.post("/admin/rebuild", dependencies=[Depends(verify_admin_token)])
    async def rebuild_indexes(request: Request) -> Dict[str, Any]:
        """Trigger knowledge base rebuild."""
        import subprocess
        import sys

        try:
            # Run build_indexes.py script
            result = subprocess.run(
                [sys.executable, "scripts/build_indexes.py"],
                cwd=Path(__file__).resolve().parent.parent.parent,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            success = result.returncode == 0
            output = result.stdout if success else result.stderr

            # Get index counts
            rag_service = getattr(request.app.state, "rag_service", None)
            index_count = 0
            if rag_service and rag_service.ready:
                index_count = rag_service.index_count

            return {
                "status": "ok" if success else "error",
                "success": success,
                "returncode": result.returncode,
                "output": output[-2000:] if output else "",  # Last 2000 chars
                "index_count": index_count,
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "success": False,
                "error": "Rebuild timed out after 5 minutes",
            }
        except Exception as e:
            return {
                "status": "error",
                "success": False,
                "error": str(e),
            }

    @app.post("/admin/eval", dependencies=[Depends(verify_admin_token)])
    async def run_eval() -> Dict[str, Any]:
        """Run evaluation tests."""
        import subprocess
        import sys

        eval_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "run_eval.py"

        if not eval_script.exists():
            return {
                "status": "not_configured",
                "configured": False,
                "message": "Eval runner not found at scripts/run_eval.py",
            }

        try:
            result = subprocess.run(
                [sys.executable, str(eval_script)],
                cwd=Path(__file__).resolve().parent.parent.parent,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Try to parse pass/fail from output
            output = result.stdout + result.stderr
            passed = result.returncode == 0

            return {
                "status": "ok" if passed else "failed",
                "configured": True,
                "passed": passed,
                "returncode": result.returncode,
                "output": output[-2000:] if output else "",
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "configured": True,
                "passed": False,
                "error": "Eval timed out",
            }
        except Exception as e:
            return {
                "status": "error",
                "configured": True,
                "passed": False,
                "error": str(e),
            }

    @app.get("/admin/status", dependencies=[Depends(verify_admin_token)])
    async def get_publish_status(request: Request) -> Dict[str, Any]:
        """Get publish/readiness status."""
        rag_service = getattr(request.app.state, "rag_service", None)

        rag_ready = False
        index_count = 0
        if rag_service:
            rag_ready = rag_service.ready
            index_count = rag_service.index_count

        # Check for indexes
        models_exist = _MODELS_DIR.exists() and any(_MODELS_DIR.iterdir())

        # Load last build info if available
        build_info = {"last_build": None, "last_error": None}
        build_status_file = _EVAL_DIR / "last_build.json"
        if build_status_file.exists():
            try:
                build_info = json.loads(build_status_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        # Load last eval info if available
        eval_info = {"last_eval_pass_rate": None, "last_eval_time": None}
        eval_status_file = _EVAL_DIR / "last_eval.json"
        if eval_status_file.exists():
            try:
                eval_info = json.loads(eval_status_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        config = _load_rag_config()

        # Determine readiness
        ready = rag_ready and models_exist and index_count > 0

        return {
            "status": "ready" if ready else "not_ready",
            "ready": ready,
            "config_version": config.get("version", 1),
            "index_count": index_count,
            "models_exist": models_exist,
            "rag_ready": rag_ready,
            "last_build": build_info.get("last_build"),
            "last_build_error": build_info.get("last_error"),
            "last_eval_pass_rate": eval_info.get("last_eval_pass_rate"),
            "last_eval_time": eval_info.get("last_eval_time"),
        }
