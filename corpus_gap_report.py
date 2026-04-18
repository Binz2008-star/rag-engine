"""Corpus gap report for indexed and non-indexed documents."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional


META_PATH = Path("storage/metadata.json")
RAW_DIR = Path("data/raw")
MIN_TEXT_THRESHOLD = 50


def normalize_name(value: str) -> str:
    return (
        value.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace(".", " ")
        .strip()
    )


def load_metadata(meta_path: Path) -> list[dict]:
    if not meta_path.exists():
        print(f"No metadata found: {meta_path}")
        return []
    return json.loads(meta_path.read_text(encoding="utf-8"))


def list_raw_files(raw_dir: Path) -> list[Path]:
    if not raw_dir.exists():
        return []
    return [p for p in raw_dir.rglob("*") if p.is_file()]


def find_best_raw_match(source: str, raw_files: list[Path]) -> Optional[Path]:
    source_norm = normalize_name(source)

    exact = []
    partial = []

    for f in raw_files:
        file_norm = normalize_name(f.name)
        if file_norm == source_norm:
            exact.append(f)
        elif source_norm in file_norm or file_norm in source_norm:
            partial.append(f)

    if exact:
        return sorted(exact, key=lambda p: len(p.name))[0]
    if partial:
        return sorted(partial, key=lambda p: len(p.name))[0]
    return None


def inspect_pdf_text(path: Path) -> tuple[str, str]:
    try:
        import fitz
    except ImportError:
        return "UNCHECKED", "PyMuPDF not available"

    try:
        doc = fitz.open(str(path))
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()

        text = "".join(text_parts).strip()
        if not text:
            return "IMAGE_ONLY", "No extractable text found"
        if len(text) < MIN_TEXT_THRESHOLD:
            return "LOW_EXTRACTABLE_TEXT", f"Only {len(text)} chars extracted"
        return "OK", ""
    except Exception as exc:
        return "ERROR", str(exc)[:80]


def inspect_file(path: Path) -> tuple[str, str]:
    if path.suffix.lower() == ".pdf":
        return inspect_pdf_text(path)
    return "OK", ""


def main() -> None:
    meta = load_metadata(META_PATH)
    raw_files = list_raw_files(RAW_DIR)

    source_chunks: dict[str, list[dict]] = defaultdict(list)
    source_types: dict[str, str] = {}

    for row in meta:
        source = row.get("source", "UNKNOWN_SOURCE")
        source_chunks[source].append(row)
        source_types[source] = row.get("doc_type", "unknown")

    indexed_statuses: dict[str, str] = {}
    indexed_reasons: dict[str, str] = {}

    print("\n=== CORPUS GAP REPORT ===\n")
    print(f"{'Source':<60} {'Type':<12} {'Chunks':<8} {'Status'}")
    print("-" * 100)

    for source in sorted(source_chunks):
        chunks = len(source_chunks[source])
        doc_type = source_types.get(source, "unknown")
        raw_match = find_best_raw_match(source, raw_files)

        status = "OK"
        reason = ""

        if raw_match is None:
            status = "RAW_MISSING"
            reason = "No matching raw file found"
        else:
            status, reason = inspect_file(raw_match)

        indexed_statuses[source] = status
        indexed_reasons[source] = reason

        print(f"{source:<60} {doc_type:<12} {chunks:<8} {status}")
        if reason:
            print(f"  Reason: {reason}")

    indexed_sources = set(source_chunks.keys())

    print("\n=== RAW FILES NOT IN INDEX ===\n")
    print(f"{'File':<60} {'Size (KB)':<12} {'Status'}")
    print("-" * 90)

    not_indexed_status_counts: dict[str, int] = defaultdict(int)

    for raw_file in sorted(raw_files):
        is_indexed = any(
            normalize_name(raw_file.name) == normalize_name(src)
            or normalize_name(raw_file.name) in normalize_name(src)
            or normalize_name(src) in normalize_name(raw_file.name)
            for src in indexed_sources
        )

        if is_indexed:
            continue

        size_kb = raw_file.stat().st_size / 1024
        status, reason = inspect_file(raw_file)
        final_status = (
            "IMAGE_ONLY_NOT_INDEXED"
            if status == "IMAGE_ONLY"
            else "LOW_TEXT_NOT_INDEXED"
            if status == "LOW_EXTRACTABLE_TEXT"
            else "NOT_INDEXED"
            if status == "OK"
            else status
        )

        not_indexed_status_counts[final_status] += 1

        print(f"{raw_file.name:<60} {size_kb:<12.1f} {final_status}")
        if reason:
            print(f"  Reason: {reason}")

    indexed_status_counts: dict[str, int] = defaultdict(int)
    for status in indexed_statuses.values():
        indexed_status_counts[status] += 1

    print("\n=== SUMMARY ===")
    print(f"Total indexed sources: {len(source_chunks)}")
    print(f"Total indexed chunks: {len(meta)}")
    print(f"Raw files discovered: {len(raw_files)}")

    print("\nIndexed source status counts:")
    for status, count in sorted(indexed_status_counts.items()):
        print(f"  {status}: {count}")

    print("\nNon-indexed raw file status counts:")
    for status, count in sorted(not_indexed_status_counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
