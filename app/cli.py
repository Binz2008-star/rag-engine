"""CLI - interactive terminal interface for RAG Assistant."""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import requests

from app.config import OLLAMA_BASE_URL
from app.query_logger import log_query
from app.rag_pipeline import RagPipeline

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
EVAL_SCRIPT  = PROJECT_ROOT / "eval_runner.py"


def _check_ollama() -> None:
    base = OLLAMA_BASE_URL.removesuffix("/api")
    try:
        requests.get(f"{base}/", timeout=5).raise_for_status()
    except Exception:
        logger.error("Ollama is not running. Start it with: ollama serve")
        sys.exit(1)


def main() -> None:
    # Windows UTF-8 fix for Arabic output
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass  # fallback silently if not supported

    parser = argparse.ArgumentParser(
        description="RAG Assistant v1.2 - Query your documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                    Interactive mode
  python run.py --rebuild          Force index rebuild
  python run.py --eval             Run evaluation suite
  python run.py --debug            Enable debug logging
        """,
    )
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild of the vector index")
    parser.add_argument("--eval",    action="store_true", help="Run evaluation suite and report metrics")
    parser.add_argument("--debug",   action="store_true", help="Enable debug logging for retrieval")
    args = parser.parse_args()

    # ── Logging setup (before any output) ────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── --eval: delegate to eval_runner, then exit ───────────────────────────
    if args.eval:
        result = subprocess.run([sys.executable, str(EVAL_SCRIPT)], cwd=str(PROJECT_ROOT))
        sys.exit(result.returncode)

    # ── Ollama check ─────────────────────────────────────────────────────────
    _check_ollama()

    # ── Pipeline init ─────────────────────────────────────────────────────────
    pipeline = RagPipeline()
    try:
        try:
            pipeline.build_index(force_rebuild=args.rebuild)
        except Exception as e:
            logger.error("Failed to build index: %s", e)
            sys.exit(1)

        pipeline.warmup()
        logger.info("Ready — %d chunks indexed. Type 'exit' to quit.\n",
                    len(pipeline.vector_store.chunks))

        while True:
            try:
                q = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not q:
                continue
            if q.lower() in {"exit", "quit"}:
                break

            try:
                response = pipeline.query(q)

                print("\n=== Answer ===")
                print(response.answer)

                if response.sources:
                    print("\n=== Sources ===")
                    for src in response.sources:
                        print(f"  • {src['source']} ({src['chunk_id']})")

                total = response.retrieval_time + response.generation_time
                print(f"\n[retrieval {response.retrieval_time:.2f}s | "
                      f"generation {response.generation_time:.2f}s | "
                      f"total {total:.2f}s]\n")

                # Log query for analytics
                log_query(
                    query=q,
                    answer=response.answer,
                    sources=response.sources,
                    retrieval_time=response.retrieval_time,
                    generation_time=response.generation_time,
                )

            except Exception as e:
                logger.error("Query error: %s", e)

    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
