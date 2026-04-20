"""Minimal manual-ingestion script.

Reads a suggestions report (produced by `analysis.suggestions`) and
copies every suggested document that is available locally in the
inbox directory into the corpus directory consumed by
`scripts/build_indexes.py`.

Scope is deliberately narrow:
    * file system only — no downloads, no scraping, no APIs
    * skips files that are already in the corpus (idempotent)
    * skips suggestions where the source file is not staged in the inbox
    * prints a concise per-file report

After running this, trigger a reindex manually:

    python scripts/build_indexes.py
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Iterable

# Make `from app.config import ...` work when invoked as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.config import DATA_DIR  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_SUGGESTIONS_PATH = _REPO_ROOT / "reports" / "suggestions.json"
_DEFAULT_INBOX = _REPO_ROOT / "data" / "inbox"


def _extract_docs(suggestions: Iterable[dict]) -> list[str]:
    """Flatten suggested documents, preserving order and deduplicating."""
    seen: dict[str, None] = {}
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        for doc in item.get("suggested_documents") or []:
            if isinstance(doc, str) and doc and doc not in seen:
                seen[doc] = None
    return list(seen.keys())


def ingest(
    suggestions: list[dict],
    *,
    inbox: Path,
    corpus: Path,
) -> dict[str, list[str]]:
    """Copy staged inbox files into the corpus directory.

    Returns a report of ingested / skipped_existing / missing_in_inbox
    document names so callers can log and decide whether to reindex.
    """
    corpus.mkdir(parents=True, exist_ok=True)

    ingested: list[str] = []
    skipped_existing: list[str] = []
    missing_in_inbox: list[str] = []

    for doc in _extract_docs(suggestions):
        src = inbox / doc
        dst = corpus / doc

        if dst.exists():
            skipped_existing.append(doc)
            continue
        if not src.exists():
            missing_in_inbox.append(doc)
            continue

        shutil.copy2(src, dst)
        ingested.append(doc)

    return {
        "ingested": ingested,
        "skipped_existing": skipped_existing,
        "missing_in_inbox": missing_in_inbox,
    }


def _load_suggestions(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Suggestions file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Suggestions file must contain a JSON list; got {type(data).__name__}")
    return data


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy suggested documents from inbox into corpus.")
    parser.add_argument(
        "--suggestions",
        type=Path,
        default=_DEFAULT_SUGGESTIONS_PATH,
        help="Path to suggestions.json produced by analysis.suggestions.",
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=_DEFAULT_INBOX,
        help="Directory where candidate documents are staged.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DATA_DIR,
        help="Target corpus directory consumed by build_indexes.py.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        suggestions = _load_suggestions(args.suggestions)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        logger.error("%s", exc)
        return 2

    report = ingest(suggestions, inbox=args.inbox, corpus=args.corpus)

    for doc in report["ingested"]:
        logger.info("[INGESTED] %s", doc)
    for doc in report["skipped_existing"]:
        logger.info("[SKIP existing] %s", doc)
    for doc in report["missing_in_inbox"]:
        logger.warning("[MISSING in inbox] %s", doc)

    logger.info(
        "Summary: ingested=%d, existing=%d, missing=%d",
        len(report["ingested"]),
        len(report["skipped_existing"]),
        len(report["missing_in_inbox"]),
    )

    if report["ingested"]:
        logger.info("Next step: python scripts/build_indexes.py")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
