from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass(slots=True)
class ExecutionResult:
    task_id: str
    status: str
    output: str
    started_at: float
    finished_at: float


class AgentExecutor:
    def execute(self, task_id: str, prompt: str) -> ExecutionResult:
        if prompt.startswith("[FAIL_TEST]"):
            raise RuntimeError("Controlled execution failure for reliability test")

        started_at = time()
        output = f"Execution shell accepted task: {prompt}"
        finished_at = time()
        return ExecutionResult(
            task_id=task_id,
            status="completed",
            output=output,
            started_at=started_at,
            finished_at=finished_at,
        )
