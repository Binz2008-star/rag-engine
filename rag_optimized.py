from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
import logging
import sys

import faiss
import numpy as np
import requests
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRCapabilities:
    tesseract_available: bool
    poppler_available: bool

    @property
    def image_ocr_enabled(self) -> bool:
        return self.tesseract_available

    @property
    def pdf_ocr_enabled(self) -> bool:
        return self.tesseract_available and self.poppler_available


def detect_ocr_capabilities() -> OCRCapabilities:
    return OCRCapabilities(
        tesseract_available=shutil.which("tesseract") is not None,
        poppler_available=shutil.which("pdftoppm") is not None,
    )


OCR_CAPS: OCRCapabilities | None = None


def init_ocr() -> OCRCapabilities:
    """Initialize OCR with proper ordering: configure first, then detect capabilities."""
    configured = _configure_tesseract()
    caps = detect_ocr_capabilities()

    # If pytesseract was configured with an explicit binary, treat Tesseract as available
    if configured:
        caps = OCRCapabilities(
            tesseract_available=True,
            poppler_available=caps.poppler_available,
        )

    global OCR_CAPS
    OCR_CAPS = caps

    logger.info(
        "OCR capabilities | tesseract=%s | poppler=%s | image_ocr=%s | pdf_ocr=%s",
        caps.tesseract_available,
        caps.poppler_available,
        caps.image_ocr_enabled,
        caps.pdf_ocr_enabled,
    )
    return caps


def _configure_tesseract() -> bool:
    """Configure pytesseract to use installed Tesseract binary with robust path search."""
    try:
        import pytesseract
        import os

        # Priority 1: Honor environment variable
        env_cmd = os.getenv("TESSERACT_CMD")
        if env_cmd and Path(env_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = env_cmd
            logger.info(f"Tesseract configured from env: {env_cmd}")
            return True

        # Priority 2: Honor PATH
        path_cmd = shutil.which("tesseract")
        if path_cmd:
            pytesseract.pytesseract.tesseract_cmd = path_cmd
            logger.info(f"Tesseract configured from PATH: {path_cmd}")
            return True

        # Priority 3: Windows candidate paths
        candidates = [
            Path(r"D:\tools\tesseract\tesseract.exe"),
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ]
        for path in candidates:
            if path.exists():
                pytesseract.pytesseract.tesseract_cmd = str(path)
                logger.info(f"Tesseract configured from candidates: {path}")
                return True

        logger.error("Tesseract not found in PATH, env, or candidate paths")
        return False
    except ImportError:
        logger.warning("pytesseract not installed")
        return False


STORE_DIR  = Path("D:/AI/assistant/vector_store")
INDEX_PATH = STORE_DIR / "index.faiss"
META_PATH  = STORE_DIR / "chunks.json"
HASH_PATH  = Path("D:/AI/assistant/data.hash")
OCR_CACHE_DIR = Path("D:/AI/assistant/.cache/ocr")
MAX_CONTEXT_CHARS = 3000
SUPPORTED_EXT = {".txt", ".md", ".py", ".pdf", ".docx", ".jpg", ".jpeg", ".png"}
OCR_MIN_TEXT_THRESHOLD = 50  # Characters below which we trigger OCR fallback
OCR_MAX_PAGES = None  # None = all pages, or set to int for page cap
DEBUG = False  # Set to True for verbose debug logging

# Normalized extraction status codes
class ExtractionStatus:
    NATIVE_OK = "native_ok"
    NATIVE_LOW_TEXT = "native_low_text"
    OCR_OK = "ocr_ok"
    OCR_CACHED = "ocr_cached"
    OCR_EMPTY = "ocr_empty"
    OCR_UNAVAILABLE = "ocr_unavailable"
    OCR_MISSING_DEPS = "ocr_missing_deps"
    OCR_ERROR = "ocr_error"
    OCR_POOR_QUALITY = "ocr_poor_quality"
    TEXT_OK = "text_ok"
    TEXT_EMPTY = "text_empty"
    TEXT_ERROR = "text_error"
    DOCX_OK = "docx_ok"
    DOCX_EMPTY = "docx_empty"
    DOCX_ERROR = "docx_error"


@dataclass
class Chunk:
    source: str
    text: str
    embedding: Optional[np.ndarray] = None


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, timeout: int = TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def _check_ollama(self) -> None:
        try:
            base = self.base_url.removesuffix("/api")
            r = self.session.get(f"{base}/", timeout=5)
            r.raise_for_status()
        except Exception:
            logger.error("Ollama is not running. Start it with: ollama serve")
            sys.exit(1)

    def embed_batch(self, texts: List[str], model: str = EMBED_MODEL) -> np.ndarray:
        if not texts:
            raise ValueError("embed_batch called with empty list")
        for attempt in range(MAX_RETRIES):
            try:
                r = self.session.post(
                    f"{self.base_url}/embed",
                    json={"model": model, "input": texts},
                    timeout=self.timeout,
                )
                r.raise_for_status()
                data = r.json()
                if "embeddings" not in data:
                    raise ValueError(f"No 'embeddings' key in response: {data}")
                arr = np.array(data["embeddings"], dtype=np.float32)
                if arr.ndim != 2 or arr.shape[0] != len(texts):
                    raise ValueError(f"Unexpected embedding shape: {arr.shape}")
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                arr /= norms
                return arr
            except Exception as e:
                logger.warning(f"Embed attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
        # This line should never be reached due to the raise in the last attempt
        raise RuntimeError("Failed to embed after all retries")

    def chat(self, prompt: str, model: str = CHAT_MODEL, stream: bool = True) -> str:
        for attempt in range(MAX_RETRIES):
            try:
                r = self.session.post(
                    f"{self.base_url}/chat",
                    json={
                        "model": model,
                        "stream": stream,
                        "messages": [{"role": "user", "content": prompt}],
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                            "num_predict": NUM_PREDICT,
                        },
                    },
                    stream=stream,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                if stream:
                    output = ""
                    for line in r.iter_lines():
                        if not line:
                            continue
                        try:
                            token = json.loads(line).get("message", {}).get("content", "")
                        except json.JSONDecodeError:
                            continue
                        print(token, end="", flush=True)
                        output += token
                    print()
                    return output
                else:
                    data = r.json()
                    return data.get("message", {}).get("content") or data["message"]["content"]
            except Exception as e:
                logger.warning(f"Chat attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(2 ** attempt)
        # This line should never be reached due to the raise in the last attempt
        raise RuntimeError("Failed to chat after all retries")

    def warmup(self) -> None:
        logger.info("Warming up model (eliminates first-query lag)...")
        try:
            self.chat("ping", stream=False)
            logger.info("Warmup complete.")
        except Exception as e:
            logger.warning(f"Warmup failed (non-fatal): {e}")


class VectorStore:
    def __init__(self):
        self.chunks: List[Chunk] = []
        self.index: Optional[faiss.IndexFlatIP] = None

    def save(self, store_dir: Path) -> None:
        store_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(store_dir / "index.faiss"))
        meta = [{"source": c.source, "text": c.text} for c in self.chunks]
        (store_dir / "chunks.json").write_text(
            json.dumps(meta, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"Saved {len(self.chunks)} chunks → {store_dir}")

    def load(self, store_dir: Path) -> None:
        self.index = faiss.read_index(str(store_dir / "index.faiss"))
        meta = json.loads((store_dir / "chunks.json").read_text(encoding="utf-8"))
        self.chunks = [Chunk(source=m["source"], text=m["text"]) for m in meta]
        if self.index and self.index.ntotal != len(self.chunks):
            raise ValueError("Corrupt cache: chunk/index count mismatch — delete vector_store/")
        logger.info(f"Loaded {len(self.chunks)} chunks from FAISS index.")

    def search(self, query_embedding: np.ndarray, top_k: int = TOP_K) -> List[Chunk]:
        if self.index is None or self.index.ntotal == 0:
            return []
        top_k = min(top_k, self.index.ntotal)
        query = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(query, top_k)
        return [self.chunks[i] for i in indices[0] if i >= 0]


def compute_data_hash(folder: Path) -> str:
    hasher = hashlib.md5()
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXT:
            try:
                hasher.update(path.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()


def is_arabic(text: str) -> bool:
    """Detect if text contains Arabic characters."""
    return any('\u0600' <= c <= '\u06FF' for c in text)


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text (hamza variants, alef maqsura, diacritics)."""
    import re
    text = re.sub(r"[إأآ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و")
    text = text.replace("ئ", "ي")
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)  # Remove diacritics
    return re.sub(r"\s+", " ", text).strip()


def translate_arabic_to_english(text: str, client: OllamaClient) -> str:
    """Translate Arabic text to English using the LLM."""
    prompt = f"Translate this Arabic text to English. Return only the English translation, no explanations:\n\n{text}"
    try:
        return client.chat(prompt, stream=False).strip()
    except Exception as e:
        logger.warning(f"Arabic translation failed: {e}")
        return text  # Fallback to original if translation fails


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if overlap >= size:
        raise ValueError(f"CHUNK_OVERLAP ({overlap}) must be smaller than CHUNK_SIZE ({size})")
    text = " ".join(text.split())
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            for sep in [". ", "! ", "? ", "\n"]:
                last = text.rfind(sep, start, end)
                if last > start:
                    end = last + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = max(0, end - overlap)
        if end >= len(text):
            break
    return chunks


def _extract_text_native_pdf(path: Path) -> str:
    """Extract text using PyMuPDF (native PDF text layer)."""
    try:
        import fitz
        with fitz.open(str(path)) as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception as e:
        logger.warning(f"Native PDF extraction failed [{path.name}]: {e}")
        return ""


def _extract_text_ocr_pdf(path: Path) -> str:
    """Extract text using OCR (for scanned/image PDFs)."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        from concurrent.futures import ThreadPoolExecutor

        logger.info(f"Running OCR on [{path.name}]...")

        # Convert PDF to images with configurable page limit
        if OCR_MAX_PAGES:
            images = convert_from_path(str(path), dpi=200, first_page=1, last_page=OCR_MAX_PAGES)
        else:
            images = convert_from_path(str(path), dpi=200)

        # Parallel OCR processing with timeout
        def ocr_image(img):
            try:
                return pytesseract.image_to_string(img, timeout=10)
            except RuntimeError:
                logger.warning("OCR timeout for page")
                return ""
            except Exception as e:
                logger.warning(f"OCR failed for page: {e}")
                return ""

        with ThreadPoolExecutor(max_workers=4) as executor:
            texts = list(executor.map(ocr_image, images))

        return "\n".join(texts)

    except ImportError as e:
        logger.error(f"OCR dependencies missing: {e}. Install: pip install pytesseract pdf2image pillow")
        return ""
    except Exception as e:
        logger.error(f"OCR failed [{path.name}]: {e}")
        return ""


def _get_ocr_cache_path(path: Path) -> Path:
    """Get cache path for OCR result based on file content hash and OCR settings."""
    content_hash = hashlib.md5(path.read_bytes()).hexdigest()
    # Include OCR settings in cache key to invalidate on configuration changes
    settings_key = json.dumps({"dpi": 200, "max_pages": OCR_MAX_PAGES}, sort_keys=True)
    combined_key = hashlib.md5(f"{content_hash}:{settings_key}".encode()).hexdigest()
    return OCR_CACHE_DIR / f"{combined_key}.txt"


def _extract_text_pdf(path: Path) -> Tuple[str, str]:
    """
    Extract text from PDF with OCR fallback.
    Returns (text, status) tuple with normalized status codes.
    """
    # Step 1: Native extraction
    text = _extract_text_native_pdf(path)
    native_len = len(text.strip())

    # Step 2: Check if image OCR is available
    if not OCR_CAPS or not OCR_CAPS.image_ocr_enabled:
        logger.warning(f"Image [{path.name}]: OCR not available, returning empty text")
        return "", ExtractionStatus.OCR_UNAVAILABLE

    # Step 3: Check OCR availability
    if not OCR_CAPS or not OCR_CAPS.pdf_ocr_enabled:
        return text, ExtractionStatus.NATIVE_LOW_TEXT

    # Step 4: Check OCR cache
    cache_path = _get_ocr_cache_path(path)
    if cache_path.exists():
        cached_text = cache_path.read_text(encoding="utf-8", errors="ignore")
        logger.info(f"PDF [{path.name}]: OCR cache hit ({len(cached_text)} chars)")
        return cached_text, ExtractionStatus.OCR_CACHED

    # Step 5: Run OCR
    logger.warning(f"PDF [{path.name}]: Low native text ({native_len} chars), running OCR...")
    ocr_text = _extract_text_ocr_pdf(path)
    ocr_len = len(ocr_text.strip())

    # Step 6: Cache OCR result (only if quality is sufficient)
    if ocr_len >= OCR_MIN_TEXT_THRESHOLD:
        OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(ocr_text, encoding="utf-8")
        logger.info(f"PDF [{path.name}]: OCR extracted {ocr_len} chars (cached)")
        return ocr_text, ExtractionStatus.OCR_OK
    else:
        logger.warning(f"PDF [{path.name}]: OCR poor quality ({ocr_len} chars) - not cached")
        return text if native_len > 0 else ocr_text, ExtractionStatus.OCR_POOR_QUALITY


def _extract_text_image(path: Path) -> Tuple[str, str]:
    """Extract text from image using OCR. Returns (text, status) tuple."""
    if not OCR_CAPS or not OCR_CAPS.image_ocr_enabled:
        return "", ExtractionStatus.OCR_UNAVAILABLE

    try:
        import pytesseract
        from PIL import Image
        img = Image.open(path)
        text = pytesseract.image_to_string(img, timeout=10)
        text = text.strip()
        return text, ExtractionStatus.OCR_OK if text else ExtractionStatus.OCR_EMPTY
    except ImportError:
        logger.error("OCR dependencies missing for image")
        return "", ExtractionStatus.OCR_MISSING_DEPS
    except Exception as e:
        logger.error(f"Image OCR failed [{path.name}]: {e}")
        return "", ExtractionStatus.OCR_ERROR


def _extract_text(path: Path) -> Tuple[str, str]:
    """Extract text from any supported file type. Returns (text, status) tuple."""
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _extract_text_pdf(path)

    elif ext in {".jpg", ".jpeg", ".png"}:
        return _extract_text_image(path)

    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(str(path))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text, ExtractionStatus.DOCX_OK if text else ExtractionStatus.DOCX_EMPTY
        except Exception as e:
            logger.error(f"DOCX read failed [{path.name}]: {e}")
            return "", ExtractionStatus.DOCX_ERROR

    else:
        # .txt, .md, .py
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return text, ExtractionStatus.TEXT_OK if text else ExtractionStatus.TEXT_EMPTY
        except Exception as e:
            logger.error(f"Text read failed [{path.name}]: {e}")
            return "", ExtractionStatus.TEXT_ERROR


def read_files(folder: Path) -> List[Chunk]:
    if not folder.exists():
        raise FileNotFoundError(f"DATA_DIR not found: {folder}")

    chunks: List[Chunk] = []
    extraction_stats = {}
    files_scanned = 0
    files_indexed = 0
    files_skipped = 0

    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXT:
            continue

        files_scanned += 1
        content, status = _extract_text(path)
        extraction_stats[status] = extraction_stats.get(status, 0) + 1

        if not content.strip():
            files_skipped += 1
            logger.warning(f"Skipped ({status}): {path.name}")
            continue

        files_indexed += 1
        text_chunks = chunk_text(content)
        for part in text_chunks:
            chunks.append(Chunk(path.name, part))
        logger.info(f"  {path.name}: {len(text_chunks)} chunks [{status}]")

    # Log operational extraction summary
    logger.info(f"\n{'='*60}")
    logger.info(f"EXTRACTION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Files scanned: {files_scanned}")
    logger.info(f"Files indexed: {files_indexed}")
    logger.info(f"Files skipped: {files_skipped}")
    logger.info(f"Total chunks produced: {len(chunks)}")
    logger.info(f"Status breakdown:")
    for status, count in sorted(extraction_stats.items()):
        logger.info(f"  {status}: {count}")
    logger.info(f"{'='*60}\n")

    if not chunks:
        raise RuntimeError(
            f"No indexable content found in {folder}.\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXT))}\n"
            f"Extraction stats: {extraction_stats}"
        )
    return chunks


def build_vector_store(chunks: List[Chunk], client: OllamaClient) -> VectorStore:
    store = VectorStore()
    all_embeddings: List[np.ndarray] = []
    total = len(chunks)
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"Embedding batch {batch_num}/{n_batches} ({len(batch)} chunks)")
        embeddings = client.embed_batch([c.text for c in batch])
        for chunk, emb in zip(batch, embeddings):
            chunk.embedding = emb
            all_embeddings.append(emb)

    store.chunks = list(chunks)
    embeddings = np.array(all_embeddings, dtype=np.float32)
    dim = embeddings.shape[1]
    store.index = faiss.IndexFlatIP(dim)
    if store.index:
        store.index.add(embeddings)
    logger.info(f"FAISS index built: {len(store.chunks)} chunks, dim={dim}")
    return store


# Legacy intent boost removed - using proper reranking instead


def rerank_candidates(query: str, candidates: List[Chunk], query_emb: np.ndarray) -> List[Chunk]:
    """Hybrid score fusion reranker combining semantic, lexical, and intent signals."""
    import re
    from collections import Counter

# Legacy intent boosting removed - using semantic and lexical reranking only

    # Normalize query for matching
    query_norm = re.sub(r'[^\w\s]', ' ', query.lower())
    query_tokens = set(query_norm.split())

    # Score each candidate
    scored = []
    for chunk in candidates:
        # Normalize chunk text
        chunk_norm = re.sub(r'[^\w\s]', ' ', chunk.text.lower())
        chunk_tokens = set(chunk_norm.split())

        # Lexical overlap score
        if query_tokens:
            overlap = len(query_tokens & chunk_tokens) / len(query_tokens)
        else:
            overlap = 0.0

        # Combine semantic score (from FAISS) with lexical overlap
        semantic_score = float(np.dot(query_emb, chunk.embedding)) if chunk.embedding is not None else 0.0
        combined_score = 0.8 * semantic_score + 0.2 * overlap

        scored.append((combined_score, chunk))

    # Sort by combined score and return top chunks
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored]


def retrieve_context(store: VectorStore, query: str, client: OllamaClient) -> List[Chunk]:
    # Dual-query retrieval for Arabic
    queries = [query]
    if is_arabic(query):
        normalized = normalize_arabic(query)
        logger.info(f"Arabic query detected. Normalized: {normalized}")
        translated = translate_arabic_to_english(normalized, client)
        logger.info(f"Translated to English: {translated}")
        queries = [normalized, translated]

    # Retrieve for all queries
    all_results = []
    for q in queries:
        q_emb = client.embed_batch([q])[0]
        results = store.search(q_emb, top_k=TOP_K)
        all_results.extend(results)

    # Deduplicate by text content
    seen_texts = set()
    unique_results = []
    for chunk in all_results:
        text_hash = hashlib.md5(chunk.text.encode()).hexdigest()
        if text_hash not in seen_texts:
            seen_texts.add(text_hash)
            unique_results.append(chunk)

    # Rerank and return top 4
    if len(unique_results) > 4:
        query_emb = client.embed_batch([query])[0]
        unique_results = rerank_candidates(query, unique_results, query_emb)[:4]

    if DEBUG:
        # Debug: log retrieval details
        logger.info(f"\n{'='*60}")
        logger.info(f"QUERY: {query}")
        if len(queries) > 1:
            logger.info(f"DUAL-QUERY MODE: {len(queries)} queries used")
        logger.info(f"{'='*60}")
        logger.info(f"RETRIEVED {len(unique_results)} CHUNKS:")
        query_emb = client.embed_batch([query])[0]
        for i, chunk in enumerate(unique_results, 1):
            score = float(np.dot(query_emb, chunk.embedding)) if chunk.embedding is not None else 0.0
            preview = chunk.text[:80].replace('\n', ' ')
            logger.info(f"  {i}. score={score:.4f} | {chunk.source} | {preview}...")
        logger.info(f"{'='*60}")

    return unique_results


def build_context(context_chunks: List[Chunk]) -> str:
    parts: List[str] = []
    total = 0
    used_chunks = []
    source_counts = {}  # Track chunks per source for diversification

    for c in context_chunks:
        # Cap repeated chunks from same source (max 3 chunks per source)
        source_count = source_counts.get(c.source, 0)
        if source_count >= 3:
            if DEBUG:
                logger.info(f"  [skipped] {c.source} - already at cap (3 chunks)")
            continue

        part = f"[{c.source}]\n{c.text}"
        if total + len(part) > MAX_CONTEXT_CHARS:
            if DEBUG:
                logger.info(f"  [truncated] {c.source} - would exceed {MAX_CONTEXT_CHARS} chars")
            break
        parts.append(part)
        used_chunks.append(c.source)
        source_counts[c.source] = source_count + 1
        total += len(part)

    context = "\n\n".join(parts)
    if DEBUG:
        logger.info(f"\nCONTEXT BUILT: {len(used_chunks)} chunks, {total} chars")
        logger.info(f"SOURCES: {used_chunks}")
        logger.info(f"SOURCE COUNTS: {source_counts}")
        logger.info(f"{'='*60}")

    return context


def generate_response(query: str, context_chunks: List[Chunk], client: OllamaClient) -> str:
    if not context_chunks:
        return "Insufficient data."

    context = build_context(context_chunks)
    if not context.strip():
        return "Insufficient data."

    # Determine required terms based on query type
    required_terms = []
    query_lower = query.lower()

    if "who is robin" in query_lower or "من هو روبن" in query_lower or "من هو" in query_lower:
        required_terms = ["experience"]
    elif "services" in query_lower or "خدمات" in query_lower:
        required_terms = ["restaurants"]
    elif "company" in query_lower or "شركة" in query_lower:
        required_terms = ["established"]

    # Base prompt with strong constraints
    prompt = (
        "Answer the question using ONLY the provided context.\n\n"
        "Rules:\n"
        "- Respond in English only (unless Arabic is explicitly requested).\n"
        "- If answer is not in context, reply exactly: Insufficient data.\n\n"
        "CRITICAL:\n"
        "- Include ALL relevant facts explicitly.\n"
        "- Do NOT omit key descriptors such as:\n"
        "  - experience / years of experience\n"
        "  - environmental role or domain\n"
        "  - company establishment details\n"
        "  - service coverage (e.g. restaurants)\n"
        "- If context implies experience, you MUST state it explicitly.\n"
        "- If listing services, provide a COMPLETE list, not a partial one.\n"
        "- Do NOT return truncated phrases.\n"
        "- Do NOT include contact info unless explicitly asked.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    # Generate initial answer
    answer = client.chat(prompt)

    # Verifier-regenerator loop: retry if required terms are missing
    if required_terms and not all(term in answer.lower() for term in required_terms):
        retry_prompt = prompt + f"\n\nYour previous answer omitted required supported terms: {required_terms}. Regenerate and include them explicitly."
        answer = client.chat(retry_prompt)

    return answer


def _load_or_build(client: OllamaClient) -> VectorStore:
    current_hash = compute_data_hash(DATA_DIR)
    store = VectorStore()

    cache_valid = (
        INDEX_PATH.exists()
        and META_PATH.exists()
        and HASH_PATH.exists()
        and HASH_PATH.read_text().strip() == current_hash
    )

    if cache_valid:
        logger.info("Cache hit — loading FAISS index...")
        store.load(STORE_DIR)
    else:
        reason = "no cache" if not INDEX_PATH.exists() else "data changed"
        logger.info(f"Cache miss ({reason}) — building FAISS index...")
        chunks = read_files(DATA_DIR)
        store = build_vector_store(chunks, client)
        store.save(STORE_DIR)
        HASH_PATH.write_text(current_hash)
        logger.info("FAISS index saved.")

    return store


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    init_ocr()
    client = OllamaClient()
    client._check_ollama()

    try:
        store = _load_or_build(client)
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)

    client.warmup()
    logger.info(f"Ready — {len(store.chunks)} chunks indexed. Type 'exit' to quit.\n")

    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break

        try:
            t0 = time.perf_counter()
            context_chunks = retrieve_context(store, q, client)
            t1 = time.perf_counter()

            print("\n=== Answer ===")
            generate_response(q, context_chunks, client)
            t2 = time.perf_counter()

            print(
                f"\n[retrieval {t1-t0:.2f}s | generation {t2-t1:.2f}s | "
                f"total {t2-t0:.2f}s]"
            )
        except Exception as e:
            logger.error(f"Query error: {e}")


if __name__ == "__main__":
    main()
