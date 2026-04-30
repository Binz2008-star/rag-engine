from __future__ import annotations

import os
from pathlib import Path


def get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data" / "raw")))
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"
MODEL_REGISTRY_PATH = MODEL_DIR / "registry.jsonl"
ACTIVE_MODEL_PATH = MODEL_DIR / "active_model.json"
STORAGE_DIR = BASE_DIR / "storage"

# Event storage
EVENT_DB_PATH = LOG_DIR / "events.db"
INDEX_DIR = MODEL_DIR
FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"
DATA_HASH_PATH = STORAGE_DIR / "data.hash"

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3")
MAX_CONTEXT_CHARS = get_int_env("MAX_CONTEXT_CHARS", 4000)
TIMEOUT = get_int_env("TIMEOUT", 60)
MAX_RETRIES = get_int_env("MAX_RETRIES", 3)
NUM_PREDICT = get_int_env("NUM_PREDICT", 120)
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "true").lower() == "true"

# Canonical refusal message. The LLM system prompt instructs the model to
# emit exactly this string when it cannot answer from the retrieved
# context. Test infrastructure and metrics should import this constant
# instead of hard-coding the literal, so future prompt changes only
# require updating one place.
REFUSAL_MESSAGE = "Insufficient data."

INTENT_CLASSES = ["cv", "eco", "general"]
UNCERTAINTY_LABEL = "uncertain"
ROUTER_CONFIDENCE_THRESHOLD = 0.55

THRESHOLDS_BY_INTENT = {
    "cv": 0.40,
    "eco": 0.38,
    "general": 0.35,
    "uncertain": 0.30,
}

TOP_K = get_int_env("TOP_K", 12)
GENERATION_TOP_K = get_int_env("GENERATION_TOP_K", 7)
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
BATCH_SIZE = 32
SUPPORTED_EXTENSIONS = {".docx", ".html", ".md", ".pdf", ".txt"}
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_SEMANTIC_WEIGHT = get_float_env("RERANK_SEMANTIC_WEIGHT", 0.6)
RERANK_LEXICAL_WEIGHT = get_float_env("RERANK_LEXICAL_WEIGHT", 0.25)
RERANK_PHRASE_WEIGHT = get_float_env("RERANK_PHRASE_WEIGHT", 0.15)
RERANK_SOURCE_PRIOR_WEIGHT = get_float_env("RERANK_SOURCE_PRIOR_WEIGHT", 0.0)

TRAINING_TRIGGER_FAILURE_COUNT = 10
MIN_QUERY_LENGTH = 3

EVENT_SCHEMA_VERSION = "1.0"

# Backward-compatible aliases for the legacy CLI / FAISS pipeline.
DATA_RAW_DIR = DATA_DIR
