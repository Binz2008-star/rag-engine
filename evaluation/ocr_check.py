from __future__ import annotations

from pathlib import Path

MIN_TEXT_LEN = 200


def check_pdf_text_length(path: Path) -> bool:
    try:
        import fitz
        doc = fitz.open(str(path))
        text = "\n".join(page.get_text() for page in doc)
        return len(text.strip()) >= MIN_TEXT_LEN
    except Exception:
        return False


def check_required_pdfs(paths: list[Path]) -> dict:
    failed = [str(p) for p in paths if not check_pdf_text_length(p)]
    return {
        "ocr_presence_check": len(failed) == 0,
        "failed_files": failed,
    }


def check_ocr_presence(data_dir: Path) -> dict:
    """
    Check OCR presence for all PDFs in the data directory.

    Returns a dict with:
    - ocr_presence_check: True if all PDFs have sufficient text
    - pdf_status: dict mapping PDF paths to their text length status
    """
    pdf_files = list(data_dir.glob("*.pdf")) + list(data_dir.rglob("*.pdf"))

    pdf_status = {}
    all_passed = True

    for pdf_path in pdf_files:
        has_text = check_pdf_text_length(pdf_path)
        pdf_status[str(pdf_path)] = {
            "has_sufficient_text": has_text,
            "min_chars_required": MIN_TEXT_LEN,
        }
        if not has_text:
            all_passed = False

    return {
        "ocr_presence_check": all_passed,
        "pdf_status": pdf_status,
    }
