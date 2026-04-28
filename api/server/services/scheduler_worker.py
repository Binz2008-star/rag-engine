from __future__ import annotations

import logging
import math
import random
import threading
import time
from typing import Callable

from .task_store import TaskStore
from .scheduler_service import SchedulerService
from .execution_guard import ExecutionGuard
from .agent_executor import AgentExecutor

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 300  # 5 minutes max

# Concurrency configuration
MAX_CONCURRENT_EXECUTIONS = 5


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
        self._execution_semaphore = threading.Semaphore(MAX_CONCURRENT_EXECUTIONS)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal the worker to stop cooperatively."""
        logger.info("Scheduler worker stop requested")
        self._stop_event.set()

    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff with jitter."""
        backoff = BASE_BACKOFF_SECONDS * (2 ** retry_count)
        backoff = min(backoff, MAX_BACKOFF_SECONDS)
        # Add symmetric jitter (±10%) to avoid thundering herd
        jitter = random.uniform(-backoff * 0.1, backoff * 0.1)
        return backoff + jitter

    def _run_task(self, task_id: str) -> None:
        task = self._task_store.get_task(task_id)
        if task is None:
            logger.warning("Scheduled task not found: %s", task_id)
            return

        # Skip tasks in terminal state or already running
        # This check must happen BEFORE semaphore acquisition to prevent
        # rescheduling tasks that are currently executing
        if task.status in {"completed", "failed", "running"}:
            logger.info("Skipping scheduled task %s (already %s)", task_id, task.status)
            return

        # Acquire semaphore to limit concurrent executions
        acquired = self._execution_semaphore.acquire(blocking=False)
        if not acquired:
            logger.warning("Execution limit reached, rescheduling task %s in 2s", task_id)
            # Reschedule with short delay instead of dropping
            # Task status remains "scheduled" - this is backpressure, not a state change
            next_run_at = time.time() + 2.0
            try:
                self._scheduler.schedule(task_id, next_run_at)
            except Exception as schedule_exc:
                logger.exception("Failed to reschedule task %s: %s", task_id, schedule_exc)
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

            # Check if task can be retried
            task = self._task_store.get_task(task_id)
            if task and task.status == "failed" and task.retry_count < MAX_RETRIES:
                backoff_seconds = self._calculate_backoff(task.retry_count)
                next_run_at = time.time() + backoff_seconds
                logger.info(
                    "Rescheduling failed task %s for retry %d/%d in %.1fs",
                    task_id,
                    task.retry_count + 1,
                    MAX_RETRIES,
                    backoff_seconds,
                )
                try:
                    self._scheduler.schedule(task_id, next_run_at)
                except Exception as schedule_exc:
                    logger.exception("Failed to reschedule task %s: %s", task_id, schedule_exc)
        finally:
            self._execution_semaphore.release()

    def run_forever(self) -> None:
        logger.info("Scheduler worker started")
        try:
            while not self._stop_event.is_set():
                now = time.time()
                next_run_time = None

                # Find next scheduled task
                for item in self._scheduler.list_scheduled():
                    if item.status != "scheduled":
                        continue

                    if item.run_at <= now:
                        # Task is due, execute immediately
                        logger.info("Triggering scheduled task: %s (scheduled for %s)", item.task_id, item.run_at)
                        try:
                            self._run_task(item.item_id)
                        except Exception:
                            logger.exception("Failed to run scheduled task: %s", item.task_id)
                    else:
                        # Track next run time
                        if next_run_time is None or item.run_at < next_run_time:
                            next_run_time = item.run_at

                # Sleep until next task is due or default interval, with stop check
                if next_run_time is not None:
                    sleep_duration = max(0, next_run_time - now)
                    sleep_duration = min(sleep_duration, 1.0)  # Cap at 1 second max
                else:
                    sleep_duration = 1.0  # Default polling interval

                # Check stop event during sleep for faster shutdown
                if self._stop_event.wait(timeout=sleep_duration):
                    break
        except Exception:
            logger.exception("Scheduler worker loop failed")
            raise
        finally:
            logger.info("Scheduler worker stopped")
