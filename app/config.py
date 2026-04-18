from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data" / "raw")))
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"
MODEL_REGISTRY_PATH = MODEL_DIR / "registry.jsonl"
ACTIVE_MODEL_PATH = MODEL_DIR / "active_model.json"

# Event storage
EVENT_DB_PATH = LOG_DIR / "events.db"
INDEX_DIR = MODEL_DIR

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2")
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
TIMEOUT = int(os.getenv("TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

INTENT_CLASSES = ["cv", "eco", "general"]
UNCERTAINTY_LABEL = "uncertain"
ROUTER_CONFIDENCE_THRESHOLD = 0.55

THRESHOLDS_BY_INTENT = {
    "cv": 0.40,
    "eco": 0.38,
    "general": 0.35,
    "uncertain": 0.30,
}

TOP_K = 5
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
BATCH_SIZE = 32

TRAINING_TRIGGER_FAILURE_COUNT = 10
MIN_QUERY_LENGTH = 3

EVENT_SCHEMA_VERSION = "1.0"
