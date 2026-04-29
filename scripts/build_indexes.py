from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path so "app", "retrieval", etc. resolve
# without requiring the caller to set PYTHONPATH manually.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BATCH_SIZE, CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR  # noqa: E402
from app.models import Chunk  # noqa: E402
from retrieval.embeddings import Embedder  # noqa: E402
from retrieval.faiss_index import FaissIndex  # noqa: E402

EXPECTED_DOC_MATCHERS = {
    "cv": ("cv", "deliveroo"),
    "eco": ("eco_company_profile", "eco technology", "clients", "pricing", "services"),
}

# Stems (filename without extension) that map explicitly to 'eco' intent.
# Business documents about ECO Technology's operations, pricing, clients,
# and service offerings belong under the eco corpus even though the
# filename itself does not contain "eco" or "company".
_ECO_DOC_STEMS: frozenset[str] = frozenset({
    "clients",
    "pricing",
    "services",
    "grease_traps",
    "maintenance",
    "operations",
})


def sanitize_text(text: str) -> str:
    """Remove OCR artifacts: specific emoji characters only."""
    # Remove only common emojis that are clearly OCR artifacts
    cleaned = "".join(
        c for c in text
        if not (
            (ord(c) >= 0x1F600 and ord(c) <= 0x1F64F)  # Emoticons
            or (ord(c) >= 0x2700 and ord(c) <= 0x27BF)    # Dingbats
            or c in "✅✓✔❌✗✘🔧🏭🔹"  # Common OCR artifact emojis
        )
    )
    return cleaned


def chunk_text(text: str, source: str, path: str, doc_type: str) -> list[Chunk]:
    text = sanitize_text(text)
    text = " ".join(text.split())
    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        part = text[start:end].strip()
        if part:
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_type}_{source}_{index:04d}",
                    source=source,
                    text=part,
                    path=path,
                    doc_type=doc_type,
                    offset=start,
                )
            )
            index += 1
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)

    return chunks


def classify_doc(path: Path) -> str:
    stem = path.stem.lower()
    name = path.name.lower()

    # Explicit stem mapping for known eco business documents
    if stem in _ECO_DOC_STEMS:
        return "eco"

    # Keyword matching
    if "cv" in name or "resume" in name or "deliveroo" in name:
        return "cv"
    if (
        "eco" in name
        or "company" in name
        or "grease" in name
        or "wastewater" in name
        or "environmental" in name
        or "sludge" in name
    ):
        return "eco"
    return "general"


def load_text(path: Path, ocr_tracking: dict) -> str:
    try:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".py"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            from scripts.ocr_helper import extract_text_with_ocr_fallback

            text, used_ocr, ocr_failed = extract_text_with_ocr_fallback(path)
            if used_ocr:
                ocr_tracking["ocr_used_files"].append(path.name)
                print(f"OCR fallback used: {path.name}")
            if ocr_failed:
                ocr_tracking["ocr_failed_files"].append(path.name)
                print(f"OCR failed: {path.name}")
            if len(text.strip()) < 200:
                ocr_tracking["low_text_files"].append(path.name)
                print(f"LOW TEXT WARNING: {path.name} ({len(text.strip())} chars)")
            return text
        if suffix == ".docx":
            from docx import Document

            document = Document(str(path))
            return "\n".join(paragraph.text for paragraph in document.paragraphs)
        return ""
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return ""


def build_grouped_chunks(debug: bool) -> tuple[dict[str, list[Chunk]], dict[str, list[str]], dict]:
    grouped: dict[str, list[Chunk]] = {"cv": [], "eco": [], "general": []}
    loaded_docs: dict[str, list[str]] = {"cv": [], "eco": [], "general": []}
    ocr_tracking = {
        "ocr_used_files": [],
        "ocr_failed_files": [],
        "low_text_files": [],
    }

    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".pdf", ".docx", ".py"}:
            continue
        doc_type = classify_doc(path)
        try:
            text = load_text(path, ocr_tracking)
        except Exception as exc:
            if debug:
                print(f"skipped unreadable doc={path.name} error={exc}")
            continue
        if not text.strip():
            continue
        doc_chunks = chunk_text(text, path.name, str(path), doc_type)
        if not doc_chunks:
            continue
        grouped[doc_type].extend(doc_chunks)
        loaded_docs[doc_type].append(path.name)
        if debug:
            print(
                f"loaded doc={path.name} doc_type={doc_type} "
                f"chunks={len(doc_chunks)} chars={len(text)}"
            )

    print(f"OCR used for {len(ocr_tracking['ocr_used_files'])} files: {ocr_tracking['ocr_used_files']}")
    print(f"OCR failed for {len(ocr_tracking['ocr_failed_files'])} files: {ocr_tracking['ocr_failed_files']}")
    print(f"Low-text warnings for {len(ocr_tracking['low_text_files'])} files: {ocr_tracking['low_text_files']}")

    return grouped, loaded_docs, ocr_tracking


def validate_expected_docs(loaded_docs: dict[str, list[str]]) -> list[str]:
    missing: list[str] = []
    lowered = {
        intent: [name.lower() for name in names]
        for intent, names in loaded_docs.items()
    }

    for intent, matchers in EXPECTED_DOC_MATCHERS.items():
        docs = lowered.get(intent, [])
        if not any(any(matcher in name for matcher in matchers) for name in docs):
            missing.append(intent)

    return missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    grouped, loaded_docs, ocr_tracking = build_grouped_chunks(debug=args.debug)
    missing = validate_expected_docs(loaded_docs)

    for intent, chunks in grouped.items():
        print(f"doc_type={intent} docs={len(loaded_docs[intent])} chunks={len(chunks)}")

    if missing:
        raise SystemExit(f"Missing expected docs for: {', '.join(sorted(missing))}")

    if not grouped["cv"] or not grouped["eco"]:
        raise SystemExit("Expected CV and ECO corpora to contain at least one chunk each")

    embedder = Embedder()
    out_dir = Path("models")
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, chunks in grouped.items():
        if not chunks:
            continue

        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]
            embeddings = embedder.embed_batch([chunk.text for chunk in batch])
            for chunk, emb in zip(batch, embeddings):
                chunk.embedding = emb

        index = FaissIndex(name=name)
        index.build(chunks)
        index.save(out_dir)
        print(f"Built index: {name} ({len(chunks)} chunks)")


if __name__ == "__main__":
    main()
