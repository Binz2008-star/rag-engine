"""
Diagnose retrieval issues by running a query through the full retrieval
pipeline with verbose output at every step.

Usage:
    python scripts/diagnose_retrieval.py "What are your grease trap prices?"
    python scripts/diagnose_retrieval.py --query "pricing" --index-dir models
    python scripts/diagnose_retrieval.py --skip-embed  # skip embedding, use random vector
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Bootstrap repo root so imports resolve without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faiss  # noqa: E402
from app.config import THRESHOLDS_BY_INTENT, TOP_K  # noqa: E402
from app.models import Chunk, RetrievalHit  # noqa: E402, F401


def _load_index(name: str, index_dir: Path) -> tuple[faiss.Index, list[dict]]:
    faiss_path = index_dir / f"{name}.faiss"
    json_path = index_dir / f"{name}.json"
    if not faiss_path.exists():
        raise FileNotFoundError(f"{faiss_path} not found")
    if not json_path.exists():
        raise FileNotFoundError(f"{json_path} not found")
    idx = faiss.read_index(str(faiss_path))
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    return idx, meta


def _source_summary(meta: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in meta:
        src = Path(chunk.get("source", "")).name
        counts[src] = counts.get(src, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose retrieval pipeline")
    parser.add_argument("query", nargs="?", default="What are your grease trap prices?")
    parser.add_argument("--index-dir", type=Path, default=Path("models"))
    parser.add_argument("--intent", default="eco")
    parser.add_argument("--top-k", type=int, default=TOP_K * 3)
    parser.add_argument("--skip-embed", action="store_true",
                        help="Skip embedding (use random vector) — for testing without Ollama")
    args = parser.parse_args(argv)

    index_dir: Path = args.index_dir
    intent: str = args.intent
    query: str = args.query

    # ── Step 1: Load index ──────────────────────────────────────────
    print("=" * 70)
    print(f"STEP 1: Load {intent} index from {index_dir}")
    print("=" * 70)
    try:
        faiss_idx, meta = _load_index(intent, index_dir)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}")
        return 1

    n_vectors = faiss_idx.ntotal
    dim = faiss_idx.d
    n_chunks = len(meta)
    print(f"  FAISS vectors:  {n_vectors}")
    print(f"  Metadata chunks: {n_chunks}")
    print(f"  Dimension:       {dim}")
    print(f"  Match:           {'YES' if n_vectors == n_chunks else 'NO — MISMATCH!'}")
    if n_vectors != n_chunks:
        print(f"  ERROR: {n_vectors} vectors vs {n_chunks} chunks — rebuild required")
        return 1

    sources = _source_summary(meta)
    print(f"\n  Sources in {intent} index ({len(sources)} files):")
    for src, cnt in sources.items():
        print(f"    {src:<50s}  chunks={cnt}")

    # ── Step 2: Embed query ─────────────────────────────────────────
    print()
    print("=" * 70)
    print("STEP 2: Embed query")
    print("=" * 70)
    print(f"  Query: {query!r}")

    if args.skip_embed:
        print("  [--skip-embed] Using random unit vector")
        rng = np.random.RandomState(42)
        query_vec = rng.randn(dim).astype(np.float32)
        query_vec /= np.linalg.norm(query_vec)
    else:
        try:
            from retrieval.embeddings import Embedder
            embedder = Embedder()
            query_vec = embedder.embed(query)
            print(f"  Embedding shape: {query_vec.shape}")
            print(f"  Embedding norm:  {np.linalg.norm(query_vec):.6f}")
            if query_vec.shape[0] != dim:
                print(f"  ERROR: embedding dim {query_vec.shape[0]} != index dim {dim}")
                return 1
        except Exception as exc:
            print(f"  FAIL: Embedding failed — {exc}")
            print("  Hint: Is Ollama running? Try --skip-embed for index-only diagnosis")
            return 1

    # ── Step 3: FAISS search (raw) ──────────────────────────────────
    print()
    print("=" * 70)
    print(f"STEP 3: FAISS search (top_k={args.top_k})")
    print("=" * 70)

    q = query_vec.reshape(1, -1).astype(np.float32)
    k = min(args.top_k, n_chunks)
    distances, indices = faiss_idx.search(q, k)

    print(f"  {'Rank':<6s}  {'Idx':<6s}  {'L2² dist':<12s}  {'cos sim':<12s}  {'Source':<50s}  Text preview")
    print("  " + "-" * 140)

    raw_hits: list[dict] = []
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0:
            continue
        int_idx = int(idx)
        if int_idx >= n_chunks:
            print(f"  {rank:<6d}  {int_idx:<6d}  OUT OF BOUNDS (index/metadata mismatch)")
            continue
        sim = max(0.0, 1.0 - float(dist) / 2.0)
        chunk = meta[int_idx]
        src = Path(chunk.get("source", "")).name
        text_preview = chunk.get("text", "")[:80].replace("\n", " ")
        print(f"  {rank:<6d}  {int_idx:<6d}  {float(dist):<12.6f}  {sim:<12.6f}  {src:<50s}  {text_preview}")
        raw_hits.append({"rank": rank, "idx": int_idx, "dist": float(dist),
                         "sim": sim, "source": src, "text": chunk.get("text", ""),
                         "chunk_id": chunk.get("chunk_id", "")})

    # ── Step 4: Threshold filtering ─────────────────────────────────
    print()
    print("=" * 70)
    print(f"STEP 4: Threshold filtering (intent={intent})")  # noqa: F541
    print("=" * 70)

    threshold = THRESHOLDS_BY_INTENT.get(intent, 0.35)
    print(f"  Threshold: {threshold}")
    print()

    kept = []
    dropped = []
    for hit in raw_hits:
        if hit["sim"] < threshold:
            dropped.append(hit)
        else:
            normalized = max(0.0, min(1.0, (hit["sim"] - threshold) / max(1e-8, 1.0 - threshold)))
            hit["normalized"] = normalized
            kept.append(hit)

    print(f"  KEPT ({len(kept)} hits):")
    if kept:
        for hit in kept:
            print(f"    rank={hit['rank']}  sim={hit['sim']:.6f}  norm={hit['normalized']:.6f}  "
                  f"src={hit['source']}  id={hit['chunk_id']}")
    else:
        print("    (none — all hits below threshold)")

    print(f"\n  DROPPED ({len(dropped)} hits):")
    if dropped:
        for hit in dropped[:5]:
            print(f"    rank={hit['rank']}  sim={hit['sim']:.6f} < {threshold}  "
                  f"src={hit['source']}  id={hit['chunk_id']}")
        if len(dropped) > 5:
            print(f"    ... and {len(dropped) - 5} more")
    else:
        print("    (none — all hits passed threshold)")

    # ── Step 5: Pricing boost ───────────────────────────────────────
    print()
    print("=" * 70)
    print("STEP 5: Pricing boost check")
    print("=" * 70)

    pricing_terms = {"price", "pricing", "cost", "costs", "quote",
                     "aed", "grease trap", "grease traps",
                     "size a", "size b", "size c", "size d",
                     "rate", "rates", "fee", "fees"}
    q_lower = query.lower()
    is_pricing_query = any(term in q_lower for term in pricing_terms)
    print(f"  Query is pricing-related: {is_pricing_query}")
    if is_pricing_query and kept:
        for hit in kept:
            text_lower = hit["text"].lower()
            if any(term in text_lower for term in ("price", "pricing", "aed", "cost")):
                old = hit["normalized"]
                hit["normalized"] = min(1.0, old + 0.10)
                print(f"    Boosted {hit['chunk_id']}: {old:.4f} → {hit['normalized']:.4f}")

    # ── Step 6: Pipeline post-checks ────────────────────────────────
    print()
    print("=" * 70)
    print("STEP 6: Pipeline post-checks")
    print("=" * 70)

    if not kept:
        print("  RESULT: retrieval_miss (0 hits after filtering)")
        print("  → Pipeline will return 'Insufficient data.'")
        print()
        print("  DIAGNOSIS:")
        print(f"  All {len(raw_hits)} FAISS results had cosine similarity < {threshold}")
        if raw_hits:
            best = max(raw_hits, key=lambda h: h["sim"])
            print(f"  Best hit: sim={best['sim']:.6f}  src={best['source']}")
            if best["sim"] < 0.01:
                print("  → Scores near 0 suggest L2² distances NOT converted to cosine similarity")
                print("  → Check that FaissIndex.search() has: sim = max(0.0, 1.0 - dist/2.0)")
            elif best["sim"] < threshold:
                print(f"  → Best score {best['sim']:.4f} is below threshold {threshold}")
                print("  → Query may not be semantically close enough to any indexed chunks")
                print("  → Or embedding model mismatch between build and query time")
        return 1

    # Simulate reranker effect
    print(f"  Hits entering pipeline: {len(kept)}")
    print("  Reranker will recompute scores (independent of FAISS scores)")
    print("  Post-reranker gate: top hit score >= 0.20")
    print()
    print("  If reranker produces scores >= 0.20, the pipeline will generate an answer.")
    print("  If reranker produces scores < 0.20, the pipeline returns 'Insufficient data.'")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Index loaded:     YES ({n_vectors} vectors, {n_chunks} chunks)")
    print(f"  Embedding dim:    {dim}")
    print(f"  FAISS hits:       {len(raw_hits)}")
    print(f"  Above threshold:  {len(kept)}")
    print(f"  Pricing boost:    {'applied' if is_pricing_query and kept else 'n/a'}")
    if kept:
        pricing_sources = [h["source"] for h in kept if "pricing" in h["source"].lower()]
        if pricing_sources:
            print(f"  pricing.md hits:  {len(pricing_sources)} — GOOD")
        else:
            print("  pricing.md hits:  0 — pricing chunks did not survive filtering")
    return 0


if __name__ == "__main__":
    sys.exit(main())
