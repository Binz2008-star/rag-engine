from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import time
from typing import Literal

ScheduleStatus = Literal["scheduled", "cancelled"]


@dataclass(slots=True)
class ScheduledTask:
    task_id: str
    run_at: float
    status: ScheduleStatus
    created_at: float


class SchedulerService:
    def __init__(self) -> None:
        self._scheduled: dict[str, ScheduledTask] = {}
        self._lock = RLock()

    def schedule(self, task_id: str, run_at: float) -> ScheduledTask:
        task = ScheduledTask(
            task_id=task_id,
            run_at=run_at,
            status="scheduled",
            created_at=time(),
        )
        with self._lock:
            self._scheduled[task_id] = task
        return task

    def cancel(self, task_id: str) -> ScheduledTask | None:
        with self._lock:
            item = self._scheduled.get(task_id)
            if item is None:
                return None
            item.status = "cancelled"
            return item

    def list_scheduled(self) -> list[ScheduledTask]:
        with self._lock:
            return sorted(self._scheduled.values(), key=lambda item: item.run_at)
