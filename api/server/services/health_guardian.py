"""Health check utilities for system dependencies.

Checks Ollama availability, index directory, and RAG service readiness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import time

import httpx


@dataclass(slots=True)
class DependencyHealth:
    name: str
    status: str
    detail: str
    metadata: dict[str, object] | None = None


class HealthGuardian:
    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self._timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 1.0))

    async def check_ollama(self, base_url: str) -> DependencyHealth:
        normalized = base_url.rstrip("/")
        url = f"{normalized}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            return DependencyHealth(
                name="ollama",
                status="down",
                detail=f"Unreachable: {exc}",
            )

        models = payload.get("models", [])
        return DependencyHealth(
            name="ollama",
            status="ok",
            detail="Ollama reachable",
            metadata={"model_count": len(models)},
        )

    def check_index_dir(self, index_dir: str) -> DependencyHealth:
        path = Path(index_dir)

        if not path.exists():
            return DependencyHealth(
                name="index_dir",
                status="down",
                detail=f"Index directory not found: {path}",
            )

        if not path.is_dir():
            return DependencyHealth(
                name="index_dir",
                status="down",
                detail=f"Index path is not a directory: {path}",
            )

        file_count = sum(1 for child in path.iterdir() if child.is_file())
        if file_count == 0:
            return DependencyHealth(
                name="index_dir",
                status="degraded",
                detail="Index directory exists but is empty",
                metadata={"file_count": 0},
            )

        return DependencyHealth(
            name="index_dir",
            status="ok",
            detail="Index directory is present",
            metadata={"file_count": file_count},
        )

    def check_rag_service_ready(
        self,
        ready: bool,
        index_count: int | None,
    ) -> DependencyHealth:
        if not ready:
            return DependencyHealth(
                name="rag_service",
                status="down",
                detail="RAG service not ready",
                metadata={"index_count": index_count},
            )

        if index_count is None or index_count <= 0:
            return DependencyHealth(
                name="rag_service",
                status="degraded",
                detail="RAG service ready but index count is empty",
                metadata={"index_count": index_count},
            )

        return DependencyHealth(
            name="rag_service",
            status="ok",
            detail="RAG service ready",
            metadata={"index_count": index_count},
        )

    async def full_report(
        self,
        *,
        ollama_base_url: str,
        index_dir: str,
        rag_ready: bool,
        index_count: int | None,
    ) -> dict[str, object]:
        checks = [
            await self.check_ollama(ollama_base_url),
            self.check_index_dir(index_dir),
            self.check_rag_service_ready(rag_ready, index_count),
        ]

        statuses = [item.status for item in checks]
        if any(status == "down" for status in statuses):
            overall_status = "down"
        elif any(status == "degraded" for status in statuses):
            overall_status = "degraded"
        else:
            overall_status = "ok"

        return {
            "overall_status": overall_status,
            "checks": [asdict(item) for item in checks],
            "timestamp": time(),
        }
