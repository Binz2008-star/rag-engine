"""Audit document ingestion - check what files are readable and what content is extracted."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent))

from rag_optimized import _extract_text, chunk_text, SUPPORTED_EXT, DATA_DIR, init_ocr


@dataclass
class FileAudit:
    filename: str
    extension: str
    path: str
    size_bytes: int
    char_count: int
    chunk_count: int
    status: str  # "ok", "empty", "error", "skipped"
    error_msg: Optional[str] = None


def audit_file(path: Path) -> FileAudit:
    """Audit a single file."""
    ext = path.suffix.lower()
    size = path.stat().st_size if path.exists() else 0

    if ext not in SUPPORTED_EXT:
        return FileAudit(
            filename=path.name,
            extension=ext,
            path=str(path),
            size_bytes=size,
            char_count=0,
            chunk_count=0,
            status="skipped",
            error_msg=f"Unsupported extension (not in {SUPPORTED_EXT})"
        )

    try:
        text, extraction_status = _extract_text(path)
        char_count = len(text)

        if char_count == 0:
            return FileAudit(
                filename=path.name,
                extension=ext,
                path=str(path),
                size_bytes=size,
                char_count=0,
                chunk_count=0,
                status="empty",
                error_msg=f"No text extracted (status: {extraction_status})"
            )

        chunks = chunk_text(text)

        return FileAudit(
            filename=path.name,
            extension=ext,
            path=str(path),
            size_bytes=size,
            char_count=char_count,
            chunk_count=len(chunks),
            status="ok",
            error_msg=None
        )

    except Exception as e:
        return FileAudit(
            filename=path.name,
            extension=ext,
            path=str(path),
            size_bytes=size,
            char_count=0,
            chunk_count=0,
            status="error",
            error_msg=str(e)
        )


def audit_folder(folder: Path) -> list[FileAudit]:
    """Audit all files in a folder."""
    results = []

    if not folder.exists():
        print(f"ERROR: Folder does not exist: {folder}")
        return results

    files = sorted([p for p in folder.rglob("*") if p.is_file()])

    print(f"\nScanning {len(files)} files in {folder}...\n")

    for path in files:
        audit = audit_file(path)
        results.append(audit)

        # Print summary line
        status_icon = {
            "ok": "✓",
            "empty": "⚠",
            "error": "✗",
            "skipped": "-"
        }.get(audit.status, "?")

        print(f"{status_icon} {audit.filename:40} | {audit.extension:6} | {audit.size_bytes:10,} bytes | "
              f"{audit.char_count:6,} chars | {audit.chunk_count:3} chunks | {audit.status}")

        if audit.error_msg:
            print(f"    → {audit.error_msg}")

    return results


def print_summary(results: list[FileAudit]):
    """Print summary statistics."""
    total = len(results)
    ok = sum(1 for r in results if r.status == "ok")
    empty = sum(1 for r in results if r.status == "empty")
    error = sum(1 for r in results if r.status == "error")
    skipped = sum(1 for r in results if r.status == "skipped")

    total_chars = sum(r.char_count for r in results)
    total_chunks = sum(r.chunk_count for r in results)

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total files scanned:  {total}")
    print(f"  ✓ OK:             {ok}")
    print(f"  ⚠ Empty:          {empty}")
    print(f"  ✗ Error:          {error}")
    print(f"  - Skipped:        {skipped}")
    print(f"\nTotal characters:   {total_chars:,}")
    print(f"Total chunks:       {total_chunks:,}")
    print(f"{'='*80}")

    # List problematic files
    if empty > 0:
        print("\n⚠ EMPTY FILES (may need manual check):")
        for r in results:
            if r.status == "empty":
                print(f"  - {r.filename} ({r.size_bytes:,} bytes)")
                print(f"    Path: {r.path}")

    if error > 0:
        print("\n✗ ERROR FILES:")
        for r in results:
            if r.status == "error":
                print(f"  - {r.filename}: {r.error_msg}")


def main():
    """Run full audit."""
    # Initialize OCR capabilities before processing
    init_ocr()

    folder = DATA_DIR

    print(f"{'='*80}")
    print(f"INGESTION AUDIT: {folder}")
    print(f"{'='*80}")

    results = audit_folder(folder)
    print_summary(results)

    # Save detailed report
    report_path = Path("ingestion_audit.json")
    report_data = [asdict(r) for r in results]
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    main()
