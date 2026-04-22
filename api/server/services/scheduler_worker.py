from __future__ import annotations

import logging
import time
from typing import Callable

from .task_store import TaskStore
from .scheduler_service import SchedulerService
from .execution_guard import ExecutionGuard
from .agent_executor import AgentExecutor

logger = logging.getLogger(__name__)


class SchedulerWorker:
    def __init__(
        self,
        task_store: TaskStore,
        scheduler_service: SchedulerService,
        execution_guard: ExecutionGuard,
        agent_executor: AgentExecutor,
    ) -> None:
        self._task_store = task_store
        self._scheduler = scheduler_service
        self._guard = execution_guard
        self._executor = agent_executor

    def _run_task(self, task_id: str) -> None:
        task = self._task_store.get_task(task_id)
        if task is None:
            logger.warning("Scheduled task not found: %s", task_id)
            return

        # Skip tasks already in terminal state
        if task.status in {"completed", "failed"}:
            logger.info("Skipping scheduled task %s (already %s)", task_id, task.status)
            return

        logger.info("Executing scheduled task: %s (title: %s)", task_id, task.title)

        try:
            self._guard.run(
                task_id,
                lambda: self._executor.execute(task.task_id, task.prompt),
            )
            logger.info("Scheduled task completed successfully: %s", task_id)
        except Exception as exc:
            logger.exception("Scheduled task execution failed: %s", task_id, exc_info=exc)

    def run_forever(self) -> None:
        logger.info("Scheduler worker started")
        try:
            while True:
                now = time.time()

                for item in self._scheduler.list_scheduled():
                    if item.status != "scheduled":
                        continue

                    if item.run_at > now:
                        continue

                    logger.info("Triggering scheduled task: %s (scheduled for %s)", item.task_id, item.run_at)
                    try:
                        self._run_task(item.task_id)
                    except Exception:
                        logger.exception("Failed to run scheduled task: %s", item.task_id)

                time.sleep(1)
        except Exception:
            logger.exception("Scheduler worker loop failed")
            raise
