from __future__ import annotations

import io
from pathlib import Path

import fitz


def extract_text_with_ocr_fallback(pdf_path: Path, min_chars: int = 200) -> tuple[str, bool, bool]:
    """
    Extract text from PDF with OCR fallback for low-text PDFs.

    Returns:
        (text, used_ocr, ocr_failed)
    """
    document = fitz.open(str(pdf_path))
    native_text_parts: list[str] = []
    for page in document:
        native_text_parts.append(page.get_text())
    native_text = "\n".join(native_text_parts).strip()

    if len(native_text) >= min_chars:
        document.close()
        return native_text, False, False

    try:
        import pytesseract
        from PIL import Image

        ocr_text_parts: list[str] = []

        for page in document:
            matrix = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            page_text = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
            ocr_text_parts.append(page_text)

        document.close()
        ocr_text = "\n".join(ocr_text_parts).strip()

        # Accept OCR if it meets min_chars OR if native text is empty and OCR has content
        if len(ocr_text) >= min_chars:
            return ocr_text, True, False
        if len(native_text) == 0 and len(ocr_text) > 0:
            return ocr_text, True, False
        if len(ocr_text) >= len(native_text):
            return ocr_text, True, False

        return native_text, False, False

    except ImportError:
        document.close()
        return native_text, False, True
    except Exception as exc:
        document.close()
        print(f"Warning: OCR failed for {pdf_path.name}: {exc}")
        return native_text, False, True
