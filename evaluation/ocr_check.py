from __future__ import annotations

from pathlib import Path

import fitz

MIN_TEXT_LEN_STRICT = 200
MIN_TEXT_LEN_DEV = 120


def extract_with_ocr(path: Path, dpi: int, psm: str) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageOps
        import io

        doc = fitz.open(path)
        texts = []
        for page in doc:
            # Higher DPI, grayscale, contrast boost
            mat = fitz.Matrix(dpi/72, dpi/72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)

            text = pytesseract.image_to_string(img, config=f'--psm {psm} -c preserve_interword_spaces=1')
            texts.append(text)
        doc.close()
        return "\n".join(texts)
    except Exception as e:
        return ""


def check_pdf_text_length(path: Path, strict: bool = True) -> tuple[bool, int, str]:
    min_len = MIN_TEXT_LEN_STRICT if strict else MIN_TEXT_LEN_DEV

    # Pass 1: native text
    try:
        doc = fitz.open(path)
        native = "\n".join(p.get_text() for p in doc)
        doc.close()
        if len(native.strip()) >= min_len:
            return True, len(native.strip()), "native"
    except:
        native = ""

    # Pass 2: OCR 300dpi psm6
    ocr1 = extract_with_ocr(path, 300, "6")
    if len(ocr1.strip()) >= min_len:
        return True, len(ocr1.strip()), "ocr_300_psm6"

    # Pass 3: OCR 400dpi psm6
    ocr2 = extract_with_ocr(path, 400, "6")
    if len(ocr2.strip()) >= min_len:
        return True, len(ocr2.strip()), "ocr_400_psm6"

    # Pass 4: OCR 400dpi psm11 (sparse text)
    ocr3 = extract_with_ocr(path, 400, "11")
    if len(ocr3.strip()) >= min_len:
        return True, len(ocr3.strip()), "ocr_400_psm11"

    # Best effort
    best = max([native, ocr1, ocr2, ocr3], key=len)
    return False, len(best.strip()), "failed"


def check_required_pdfs(paths: list[Path], strict: bool = True) -> dict:
    results = {}
    failed = []

    for p in paths:
        passed, chars, method = check_pdf_text_length(p, strict)
        results[p.name] = {"passed": passed, "chars": chars, "method": method}
        if not passed:
            failed.append(p.name)

    return {
        "ocr_presence_check": len(failed) == 0,
        "failed_files": failed,
        "details": results
    }


def check_ocr_presence(data_dir: Path, strict: bool = True) -> dict:
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
        passed, chars, method = check_pdf_text_length(pdf_path, strict)
        pdf_status[str(pdf_path)] = {
            "has_sufficient_text": passed,
            "chars": chars,
            "method": method,
            "min_chars_required": MIN_TEXT_LEN_STRICT if strict else MIN_TEXT_LEN_DEV,
        }
        if not passed:
            all_passed = False

    return {
        "ocr_presence_check": all_passed,
        "pdf_status": pdf_status,
    }
