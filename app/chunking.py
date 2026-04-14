"""Text chunking - splits documents into searchable segments."""

import logging
import time
from typing import List

from app.config import CHUNK_SIZE, CHUNK_OVERLAP
from app.models import Chunk

logger = logging.getLogger(__name__)


def chunk_text(text: str, source: str, path: str, doc_type: str) -> List[Chunk]:
    """Split text into overlapping chunks with metadata."""
    t0 = time.perf_counter()
    text = " ".join(text.split())
    chunks: List[Chunk] = []
    start = 0
    chunk_num = 0
    iteration = 0
    max_iterations = 10000

    logger.info("Starting chunking for %s: text_length=%d", source, len(text))

    while start < len(text):
        iteration += 1
        if iteration > max_iterations:
            logger.error(
                "Chunking stuck at iteration %d: start=%d, text_length=%d",
                iteration, start, len(text)
            )
            raise RuntimeError(f"Chunking exceeded max iterations for {source}")

        if iteration % 100 == 0:
            logger.info(
                "Chunking progress: iteration=%d, start=%d, chunks=%d",
                iteration, start, len(chunks)
            )

        target_end = min(len(text), start + CHUNK_SIZE)
        end = target_end

        # Only snap to boundaries near the end of the window.
        if target_end < len(text):
            search_start = max(start, target_end - (CHUNK_SIZE // 4))
            best_pos = -1
            best_sep_len = 0

            for sep in [". ", "! ", "? ", "\n"]:
                pos = text.rfind(sep, search_start, target_end)
                if pos > best_pos:
                    best_pos = pos
                    best_sep_len = len(sep)

            if best_pos > start:
                end = best_pos + best_sep_len

        chunk_body = text[start:end].strip()
        if chunk_body:
            chunk_id = f"{doc_type}_{source}_{chunk_num:04d}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    source=source,
                    text=chunk_body,
                    path=path,
                    doc_type=doc_type,
                    offset=start,
                )
            )
            chunk_num += 1

        if end >= len(text):
            break

        new_start = max(0, end - CHUNK_OVERLAP)
        if new_start <= start:
            new_start = min(len(text), start + max(1, CHUNK_SIZE - CHUNK_OVERLAP))

        start = new_start

    elapsed = time.perf_counter() - t0
    logger.info("Chunked %s: %d chunks in %.3fs", source, len(chunks), elapsed)
    return chunks


def chunk_documents(documents: List) -> List[Chunk]:
    """Chunk all documents into segments."""
    all_chunks: List[Chunk] = []

    for i, doc in enumerate(documents, start=1):
        chunks = chunk_text(doc.text, doc.source, doc.path, doc.doc_type)
        all_chunks.extend(chunks)
        logger.info(
            "Document %d/%d: source=%s, chunks=%d, cumulative_total=%d",
            i,
            len(documents),
            doc.source,
            len(chunks),
            len(all_chunks),
        )

    logger.info("Total chunks across all documents: %d", len(all_chunks))
    return all_chunks
