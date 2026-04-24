from __future__ import annotations

import logging
import traceback
from typing import Callable, TypeVar

from .task_store import AgentTask, InvalidStateTransitionError, TaskStore

logger = logging.getLogger(__name__)

T = TypeVar("T")
MAX_RETRIES = 3


class ExecutionGuard:
    def __init__(self, task_store: TaskStore) -> None:
        self._task_store = task_store

    def run(self, task_id: str, fn: Callable[[], T]) -> T:
        task = self._task_store.get_task(task_id)
        if task is None:
            raise RuntimeError("Task not found")

        if task.status == "completed":
            raise RuntimeError("Task already completed")

        if task.retry_count >= MAX_RETRIES:
            raise RuntimeError("Max retries exceeded for task")

        if not self._task_store.can_transition_to(task_id, "running"):
            raise InvalidStateTransitionError(task.status, "running")

        updated = self._task_store.set_running(task_id)
        if updated is None:
            raise RuntimeError("Task not found")

        try:
            result = fn()
        except Exception as exc:
            error_type = exc.__class__.__name__
            msg = str(exc)
            error_message = msg[:500]

            logger.exception(
                "Guarded task execution failed",
                extra={
                    "task_id": task_id,
                    "error_type": error_type,
                },
            )

            failed = self._task_store.set_failed(
                task_id,
                error_message,
                error_type=error_type,
            )
            if failed is None:
                raise ValueError("Task not found") from exc

            raise

        completed = self._task_store.set_completed(task_id)
        if completed is None:
            raise ValueError("Task not found")

        return result
