"""Prompt building - constructs grounded prompts from retrieved context."""

from __future__ import annotations

import logging
from typing import List

from app.config import MAX_CONTEXT_CHARS
from app.models import RetrievedChunk

logger = logging.getLogger(__name__)


SYSTEM_INSTRUCTIONS = """You are Robin's local RAG assistant.

Answer strictly from the retrieved context.
Do not use outside knowledge.
If the context does not support the answer, respond exactly:
Insufficient data.

Rules:
- Use only facts present in the context.
- Do not guess or infer beyond the retrieved text.
- Keep the answer concise and direct.
- Respond in the same language as the question unless explicitly instructed otherwise.
- Cite the source filenames you used at the end under a heading: Sources

Grounding Rules (STRICT):
- Do NOT modify or paraphrase entity names, locations, or identifiers. Copy them exactly as they appear in the context.
- Do NOT treat location as nationality unless explicitly stated.
- If the answer is not explicitly stated in the context, respond: "Insufficient data."
- Do NOT infer or generalize. Only answer if the information is directly present.
- If the query asks for a specific attribute (e.g., language, nationality), only answer if that attribute is explicitly present.
- Do NOT include chunk IDs, rank labels, or bracketed metadata in the answer.
- Only include source filenames under the "Sources" section.
- Copy entity values EXACTLY (character-for-character).
- Do NOT generate variations (e.g., UAE → UAEI → UAII).

CRITICAL OUTPUT RULES:
1. Output MUST be in English only.
2. If ANY Arabic text appears → discard answer and regenerate in English.
3. If answer does not explicitly contain required facts → respond: Insufficient data.
4. Do NOT summarize — extract exact facts from context.
5. Do NOT produce partial answers.
6. Do NOT include any bracketed text or metadata.

Phase 2 Generation Contract:
- Do NOT include email addresses, phone numbers, or WhatsApp details unless the question explicitly asks for them.
- Prefer a short direct answer, then one sentence of supporting detail if available.
- Do NOT include raw contact details from context unless directly requested.
- If evidence exists, provide a clean factual answer without concatenating unrelated text.

OUTPUT DISCIPLINE:
- Respond with facts only, not summaries.
- If the context contains the needed fact, include it explicitly.
- Never output Arabic characters.
- Never output chunk metadata, rank labels, or bracketed markers.
- If the answer is unsupported, respond exactly: Insufficient data.
"""


def build_prompt(query: str, retrieved_chunks: List[RetrievedChunk]) -> str:
    """Build a grounded prompt with retrieved context."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string.")

    if not retrieved_chunks:
        return (
            f"{SYSTEM_INSTRUCTIONS}\n\n"
            "Context:\n[no context]\n\n"
            f"Question: {query}\n\n"
            "Answer:"
        )

    context = build_context(retrieved_chunks)

    # Answer-stage instruction for language control
    answer_instruction = """You must answer in English only.
If retrieved context is in Arabic or any non-English language, translate it to English internally before answering.
Do not copy Arabic text unless the user explicitly asks for it.
If a word appears malformed or concatenated (e.g., UAEIbased), correct it to the closest valid form using the context.
If the source text appears corrupted or unreadable, say so clearly and do not reproduce corrupted text."""

    prompt = (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"Context:\n{context}\n\n"
        f"{answer_instruction}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    logger.info("Built prompt with %d chars of context", len(context))
    return prompt


def build_context(retrieved_chunks: List[RetrievedChunk]) -> str:
    """Build context string from retrieved chunks, respecting max length."""
    parts: List[str] = []
    total = 0

    for rank, rc in enumerate(retrieved_chunks, start=1):
        part = (
            f"[Rank {rank} | Score {rc.score:.4f} | Source {rc.chunk.source} | "
            f"Chunk {rc.chunk.chunk_id}]\n"
            f"{rc.chunk.text.strip()}"
        )

        projected = total + len(part) + (2 if parts else 0)
        if projected > MAX_CONTEXT_CHARS:
            logger.info(
                "Context capped at %d chars; stopped before chunk %s",
                MAX_CONTEXT_CHARS,
                rc.chunk.chunk_id,
            )
            break

        parts.append(part)
        total = projected

    if not parts:
        return "[no usable context]"

    return "\n\n".join(parts)


def extract_sources(retrieved_chunks: List[RetrievedChunk]) -> List[dict[str, str]]:
    """Extract unique source information from retrieved chunks."""
    sources: List[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for rc in retrieved_chunks:
        key = (rc.chunk.source, rc.chunk.chunk_id)
        if key in seen:
            continue

        sources.append(
            {
                "source": rc.chunk.source,
                "chunk_id": rc.chunk.chunk_id,
            }
        )
        seen.add(key)

    return sources
