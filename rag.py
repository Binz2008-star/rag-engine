from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np
import requests

OLLAMA_BASE_URL = "http://localhost:11434/api"
CHAT_MODEL = "robin-assistant"
EMBED_MODEL = "nomic-embed-text"
DATA_DIR = Path(r"D:\AI\data")
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
TOP_K = 4
TIMEOUT = 120


@dataclass
class Chunk:
    source: str
    text: str
    embedding: np.ndarray | None = None


def chunk_text(text: str, size: int, overlap: int) -> List[str]:
    text = " ".join(text.split())
    chunks = []
    start = 0

    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = 0
        if end == len(text):
            break

    return chunks


def read_files(folder: Path):
    chunks = []

    for path in folder.glob("*.txt"):
        content = path.read_text(encoding="utf-8", errors="ignore")

        for part in chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP):
            chunks.append(Chunk(path.name, part))

    if not chunks:
        raise Exception("No .txt files found in D:\\AI\\data")

    return chunks


def embed(texts):
    r = requests.post(
        f"{OLLAMA_BASE_URL}/embed",
        json={"model": EMBED_MODEL, "input": texts},
    )
    data = r.json()
    arr = np.array(data["embeddings"], dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    return arr


def build_index(chunks):
    vectors = embed([c.text for c in chunks])
    for c, v in zip(chunks, vectors):
        c.embedding = v
    return chunks


def retrieve(chunks, query):
    q = embed([query])[0]
    scores = [(float(np.dot(q, c.embedding)), c) for c in chunks]
    scores.sort(reverse=True)
    return [c for _, c in scores[:TOP_K]]


def ask(prompt):
    r = requests.post(
        f"{OLLAMA_BASE_URL}/chat",
        json={
            "model": CHAT_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return r.json()["message"]["content"]


def main():
    print("Loading data...")
    chunks = build_index(read_files(DATA_DIR))

    while True:
        q = input("\n> ")
        if q in ["exit", "quit"]:
            break

        ctx = retrieve(chunks, q)
        context = "\n\n".join(c.text for c in ctx)

        prompt = f"""Use context to answer. If missing say: Insufficient data.

{context}

Question: {q}
"""

        print("\n=== Answer ===")
        print(ask(prompt))


if __name__ == "__main__":
    main()
