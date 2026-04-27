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
        from PIL import Image, ImageOps

        ocr_text_parts: list[str] = []

        for page in document:
            # Try multiple OCR strategies
            page_texts = []

            # Strategy 1: 300 DPI, psm6
            matrix = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            page_text = pytesseract.image_to_string(img, config='--psm 6 -c preserve_interword_spaces=1')
            page_texts.append(("300dpi_psm6", page_text))

            # Strategy 2: 400 DPI, psm6
            matrix = fitz.Matrix(400/72, 400/72)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            page_text = pytesseract.image_to_string(img, config='--psm 6 -c preserve_interword_spaces=1')
            page_texts.append(("400dpi_psm6", page_text))

            # Strategy 3: 400 DPI, psm11 (sparse text)
            matrix = fitz.Matrix(400/72, 400/72)
            pix = page.get_pixmap(matrix=matrix)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img)
            page_text = pytesseract.image_to_string(img, config='--psm 11 -c preserve_interword_spaces=1')
            page_texts.append(("400dpi_psm11", page_text))

            # Select best result (longest non-empty text)
            best_strategy, best_text = max(page_texts, key=lambda x: len(x[1].strip()))
            ocr_text_parts.append(best_text)

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
