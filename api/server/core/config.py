"""Runtime configuration for the API gateway.

Ollama / model defaults are deliberately not redefined here. The canonical
source is `app.config` (read by `generation.llm.LLMClient`). Duplicating
them would let the API drift away from what CI validates. The only
model-related field we keep is `chat_model`, read once at startup purely
for the health-check label.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


# Load api/.env first, then fall back to project root .env without
# overriding anything already set by api/.env.
_API_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _API_DIR.parent

load_dotenv(_API_DIR / ".env")
load_dotenv(_ROOT_DIR / ".env", override=False)


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """Immutable application settings."""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("API_APP_NAME", "RAG Assistant API")
        self.version: str = os.getenv("API_VERSION", "1.0.0")
        self.host: str = os.getenv("API_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("API_PORT", "8000"))
        self.log_level: str = os.getenv("API_LOG_LEVEL", "INFO").upper()

        self.cors_origins: List[str] = _split_csv(
            os.getenv(
                "API_CORS_ORIGINS",
                "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
            )
        )

        # Where FAISS indexes live. Must match what `scripts/build_indexes.py`
        # writes to and what `eval_runner.py` reads from.
        self.index_dir: Path = Path(
            os.getenv("API_INDEX_DIR", str(_ROOT_DIR / "models"))
        )

        # Per-request limits.
        self.max_question_length: int = int(
            os.getenv("API_MAX_QUESTION_LENGTH", "4000")
        )

        # Label-only: resolved from the project's canonical config. The
        # actual chat model used by `LLMClient` is also read from
        # `app.config.CHAT_MODEL`, so changing one without the other would
        # be a bug. Keeping both read the same env var enforces parity.
        self.chat_model: str = os.getenv("CHAT_MODEL", "qwen2:1.5b")

        # Ollama health check configuration.
        self.ollama_base_url: str = os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.ollama_required_models: List[str] = _split_csv(
            os.getenv(
                "OLLAMA_REQUIRED_MODELS",
                "nomic-embed-text,robin-assistant-opt",
            )
        )

        # Trading runtime feature flags
        self.trading_live_enabled: bool = os.getenv(
            "TRADING_LIVE_ENABLED", "false"
        ).lower() in ("true", "1", "yes")
        self.trading_exchange: str = os.getenv(
            "TRADING_EXCHANGE", "none"
        ).lower()
        self.trading_binance_api_key: Optional[str] = os.getenv(
            "TRADING_BINANCE_API_KEY"
        )
        self.trading_binance_api_secret: Optional[str] = os.getenv(
            "TRADING_BINANCE_API_SECRET"
        )
        self.trading_bybit_api_key: Optional[str] = os.getenv(
            "TRADING_BYBIT_API_KEY"
        )
        self.trading_bybit_api_secret: Optional[str] = os.getenv(
            "TRADING_BYBIT_API_SECRET"
        )
        self.trading_sandbox: bool = os.getenv(
            "TRADING_SANDBOX", "true"
        ).lower() in ("true", "1", "yes")

        # Jotform webhook configuration
        self.jotform_webhook_enabled: bool = os.getenv(
            "JOTFORM_WEBHOOK_ENABLED", "true"
        ).lower() in ("true", "1", "yes")
        self.jotform_memory_dir: Path = Path(
            os.getenv("JOTFORM_MEMORY_DIR", str(_ROOT_DIR / "data" / "jotform_memory"))
        )
        self.jotform_webhook_secret: str | None = os.getenv("JOTFORM_WEBHOOK_SECRET")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
