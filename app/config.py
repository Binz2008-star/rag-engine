from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data" / "raw"
DATA_DIR = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
DATA_RAW_DIR = DATA_DIR
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"
MODEL_DIR = BASE_DIR / "models"
STORAGE_DIR = BASE_DIR / "storage"
EVENT_LOG_PATH = LOG_DIR / "events.jsonl"
MODEL_REGISTRY_PATH = MODEL_DIR / "registry.jsonl"
ACTIVE_MODEL_PATH = MODEL_DIR / "active_model.json"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
CHAT_MODEL = os.getenv("CHAT_MODEL", "robin-assistant-opt")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "5"))
TIMEOUT = int(os.getenv("TIMEOUT", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "3000"))

INTENT_CLASSES = ["cv", "eco", "general"]
UNCERTAINTY_LABEL = "uncertain"
ROUTER_CONFIDENCE_THRESHOLD = float(os.getenv("ROUTER_CONFIDENCE_THRESHOLD", "0.60"))

THRESHOLDS_BY_INTENT = {
    "cv": 0.30,
    "eco": 0.35,
    "general": 0.40,
    "uncertain": 0.30,
}

TRAINING_TRIGGER_FAILURE_COUNT = int(os.getenv("TRAINING_TRIGGER_FAILURE_COUNT", "500"))
MIN_QUERY_LENGTH = 3
EVENT_SCHEMA_VERSION = "v1"

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".py"}

FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"
DATA_HASH_PATH = STORAGE_DIR / "data.hash"

PRODUCTION_MODE: bool = os.getenv("PRODUCTION_MODE", "false").lower() == "true"

for path in (LOG_DIR, MODEL_DIR, DATA_DIR, STORAGE_DIR, DATA_PROCESSED_DIR):
    path.mkdir(parents=True, exist_ok=True)
