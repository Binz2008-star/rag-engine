"""Central configuration for RAG Assistant v1."""

from pathlib import Path

BASE_DIR = Path(r"D:\AI\assistant")
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
DATA_PROCESSED_DIR = BASE_DIR / "data" / "processed"
STORAGE_DIR = BASE_DIR / "storage"

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434/api"
CHAT_MODEL = "robin-assistant"
EMBED_MODEL = "nomic-embed-text"

# Chunking settings
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

# Retrieval settings
TOP_K = 8
MAX_CONTEXT_CHARS = 3000

# Reranking settings (v1.4)
RERANK_ENABLED = True  # Re-enabled for v0.1.1 patch with hybrid score fusion
RERANK_SEMANTIC_WEIGHT = 0.65
RERANK_LEXICAL_WEIGHT = 0.20
RERANK_PHRASE_WEIGHT = 0.08
RERANK_SOURCE_PRIOR_WEIGHT = 0.07

# Performance settings
TIMEOUT = 300
MAX_RETRIES = 3
BATCH_SIZE = 1
NUM_PREDICT = 768

# File handling
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html"}

# Storage files
FAISS_INDEX_PATH = STORAGE_DIR / "faiss.index"
METADATA_PATH = STORAGE_DIR / "metadata.json"
DATA_HASH_PATH = STORAGE_DIR / "data.hash"
