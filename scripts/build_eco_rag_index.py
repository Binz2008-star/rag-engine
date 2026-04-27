#!/usr/bin/env python3
"""
Build ECO index from eco_rag_ready.jsonl.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import BATCH_SIZE
from app.models import Chunk
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex

INPUT_FILE = Path("models/eco_rag_ready.jsonl")
OUTPUT_DIR = Path("models")


def main():
    # Load JSONL rows
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    
    print(f"Loaded {len(rows)} rows from {INPUT_FILE}")
    
    # Convert to Chunk format
    chunks = []
    for i, row in enumerate(rows):
        chunk = Chunk(
            chunk_id=row["id"],
            source=row["source"],
            text=row["text"],
            path=f"eco_rag_ready.jsonl:{i}",
            doc_type="eco",
            offset=0,
            embedding=None
        )
        chunks.append(chunk)
    
    print(f"Converted to {len(chunks)} chunks")
    
    # Generate embeddings
    embedder = Embedder()
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        embeddings = embedder.embed_batch([chunk.text for chunk in batch])
        for chunk, emb in zip(batch, embeddings):
            chunk.embedding = emb
        print(f"Generated embeddings for batch {start//BATCH_SIZE + 1}/{(len(chunks) + BATCH_SIZE - 1)//BATCH_SIZE}")
    
    # Build FAISS index
    index = FaissIndex(name="eco")
    index.build(chunks)
    index.save(OUTPUT_DIR)
    
    print(f"Built ECO index: {len(chunks)} chunks")
    print(f"Index saved to {OUTPUT_DIR}/eco.faiss and {OUTPUT_DIR}/eco.json")


if __name__ == "__main__":
    main()
