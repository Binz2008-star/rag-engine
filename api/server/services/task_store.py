from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock
from time import time
from typing import Literal

logger = logging.getLogger(__name__)

# Resolved at import time so the store is always under <project-root>/logs/
# regardless of the process CWD.  task_store.py lives at
# api/server/services/task_store.py → parents[3] is the project root.
_DEFAULT_STORE_PATH = Path(__file__).resolve().parents[3] / "logs" / "agent_tasks.json"

TaskStatus = Literal["pending", "scheduled", "running", "completed", "failed"]


class InvalidStateTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, current_status: TaskStatus, target_status: TaskStatus):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Invalid state transition: {current_status} -> {target_status}. "
            f"Allowed transitions from {current_status}: "
            f"{_ALLOWED_TRANSITIONS.get(current_status, set())}"
        )


@dataclass(slots=True)
class AgentTask:
    task_id: str
    session_id: str | None
    user_id: str | None
    title: str
    prompt: str
    intent: str
    status: TaskStatus
    created_at: float
    updated_at: float
    error_message: str | None = None
    last_run_started_at: float | None = None
    last_run_finished_at: float | None = None
    error_type: str | None = None
    retry_count: int = 0
    run_count: int = 0
    metadata: dict = field(default_factory=dict)


_ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    "pending": {"scheduled", "running", "failed"},
    "scheduled": {"running", "failed"},
    "running": {"completed", "failed"},
    "completed": {"completed"},
    "failed": {"failed", "scheduled", "running"},
}


class TaskStore:
    """
    Thread-safe in-memory task store with atomic file persistence.

    NOTE: This implementation uses threading.RLock for single-process safety only.
    It is NOT safe for cross-process concurrent access. For distributed deployments,
    a proper distributed lock or database-backed store is required.
    """

    def __init__(self, file_path: str | Path | None = None) -> None:
        self._file_path = Path(file_path) if file_path is not None else _DEFAULT_STORE_PATH
        self._lock = RLock()
        self._tasks: dict[str, AgentTask] = {}
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self._file_path.exists():
            return

        try:
            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
            loaded: dict[str, AgentTask] = {}
            for item in raw:
                # Ensure backward compatibility: add missing fields with defaults
                item.setdefault("error_type", None)
                item.setdefault("retry_count", 0)
                item.setdefault("run_count", 0)
                item.setdefault("metadata", {})
                task = AgentTask(**item)
                loaded[task.task_id] = task
            self._tasks = loaded
        except Exception:
            logger.exception("Failed to load task store from %s", self._file_path)
            self._tasks = {}

    def _atomic_write(self, payload: str) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        for attempt in range(max_retries):
            fd, temp_path = tempfile.mkstemp(
                prefix=f"{self._file_path.name}.",
                suffix=".tmp",
                dir=str(self._file_path.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self._file_path)
                return
            except OSError as exc:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    "Atomic write attempt %d failed for %s, retrying",
                    attempt + 1,
                    self._file_path,
                    exc_info=True,
                )
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        logger.warning("Failed to remove temp task store file %s", temp_path)

    def _persist(self) -> None:
        tasks_data = []
        for task in self._tasks.values():
            task_dict = {
                "task_id": task.task_id,
                "session_id": task.session_id,
                "user_id": task.user_id,
                "title": task.title,
                "prompt": task.prompt,
                "intent": task.intent,
                "status": task.status,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "error_message": task.error_message,
                "last_run_started_at": task.last_run_started_at,
                "last_run_finished_at": task.last_run_finished_at,
                "error_type": task.error_type,
                "retry_count": task.retry_count,
                "run_count": task.run_count,
                "metadata": task.metadata,
            }
            tasks_data.append(task_dict)
        payload = json.dumps(
            tasks_data,
            indent=2,
            ensure_ascii=False,
        )
        self._atomic_write(payload)

    def _transition(self, task: AgentTask, new_status: TaskStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(task.status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(task.status, new_status)

        now = time()
        task.status = new_status
        task.updated_at = now

        if new_status == "running":
            task.last_run_started_at = now
            task.error_message = None
            task.error_type = None
            task.run_count += 1

        if new_status in {"completed", "failed"}:
            task.last_run_finished_at = now

        if new_status == "failed":
            task.retry_count += 1

    def _validate_task_data(
        self,
        task_id: str,
        title: str,
        prompt: str,
        intent: str,
    ) -> None:
        if not task_id or not isinstance(task_id, str):
            raise ValueError("task_id must be a non-empty string")
        if not title or not isinstance(title, str):
            raise ValueError("title must be a non-empty string")
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")
        if not intent or not isinstance(intent, str):
            raise ValueError("intent must be a non-empty string")
        if task_id in self._tasks:
            raise ValueError(f"Task with id {task_id} already exists")

    def create_task(
        self,
        task_id: str,
        title: str,
        prompt: str,
        intent: str,
        session_id: str | None,
        user_id: str | None,
        status: TaskStatus = "pending",
    ) -> AgentTask:
        self._validate_task_data(task_id, title, prompt, intent)
        now = time()
        task = AgentTask(
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            title=title,
            prompt=prompt,
            intent=intent,
            status=status,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task_id] = task
            self._persist()
        return task

    def get_task(self, task_id: str) -> AgentTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, session_id: str | None = None) -> list[AgentTask]:
        with self._lock:
            tasks = list(self._tasks.values())
            if session_id:
                tasks = [task for task in tasks if task.session_id == session_id]
            return sorted(tasks, key=lambda task: task.created_at, reverse=True)

    def update_status(self, task_id: str, status: TaskStatus) -> AgentTask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            self._transition(task, status)
            self._persist()
            return task

    def set_scheduled(self, task_id: str) -> AgentTask | None:
        return self.update_status(task_id, "scheduled")

    def set_running(self, task_id: str) -> AgentTask | None:
        return self.update_status(task_id, "running")

    def set_completed(self, task_id: str) -> AgentTask | None:
        return self.update_status(task_id, "completed")

    def set_failed(
        self,
        task_id: str,
        error_message: str,
        error_type: str | None = None,
    ) -> AgentTask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            self._transition(task, "failed")
            task.error_message = error_message
            task.error_type = error_type
            self._persist()
            return task

    def can_transition_to(self, task_id: str, target_status: TaskStatus) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False
            allowed = _ALLOWED_TRANSITIONS.get(task.status, set())
            return target_status in allowed

    def get_current_state(self, task_id: str) -> TaskStatus | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.status if task else None
