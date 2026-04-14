from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
CHAT_MODEL = os.getenv("CHAT_MODEL", "robin-assistant")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
DATA_DIR = Path(os.getenv("DATA_DIR", r"D:\AI\data"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("TOP_K", "4"))
TIMEOUT = int(os.getenv("TIMEOUT", "60"))

GPU_ENABLED = os.getenv("GPU_ENABLED", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "768"))
