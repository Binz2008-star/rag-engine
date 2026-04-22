from __future__ import annotations

from dataclasses import dataclass, asdict
from threading import RLock
from time import time
from typing import Literal
import json
from pathlib import Path

TaskStatus = Literal["pending", "scheduled", "running", "completed", "failed"]


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


class TaskStore:
    def __init__(self, file_path: str = "logs/agent_tasks.json") -> None:
        self._file_path = Path(file_path)
        self._lock = RLock()
        self._tasks: dict[str, AgentTask] = {}
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self._file_path.exists():
            return
        try:
            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
            for item in raw:
                task = AgentTask(**item)
                self._tasks[task.task_id] = task
        except Exception:
            self._tasks = {}

    def _persist(self) -> None:
        payload = [asdict(task) for task in self._tasks.values()]
        self._file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

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
            task.status = status
            task.updated_at = time()
            self._persist()
            return task
