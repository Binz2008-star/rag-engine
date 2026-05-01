"""OCR script for image-only certificate PDFs."""
import fitz
from pathlib import Path
import pytesseract
from PIL import Image, ImageOps
import io
import re

# Image-only certificate PDFs
CERTIFICATE_PDFS = [
    "data/raw/Sellora_Process_Automation_Certificate.pdf",
    "data/raw/Sellora_WhatsApp_Operations_Certificate.pdf",
]

def normalize_certificate(raw_text: str) -> str:
    """Extract structured entities from certificate OCR text."""
    lines = raw_text.split('\n')
    structured = []

    # Extract potential title (usually first non-empty line)
    for line in lines:
        if line.strip():
            structured.append(f"Certificate Title: {line.strip()}")
            break

    # Extract potential issuer (lines containing "issued by", "from", "company", "ltd", etc.)
    issuer_patterns = [
        r'issued by\s*[:\.]?\s*(.+)',
        r'from\s+([A-Z][A-Za-z\s]+(?:Company|Ltd|LLC|Corporation))',
        r'([A-Z][A-Za-z\s]+(?:Company|Ltd|LLC|Corporation))',
    ]
    for line in lines:
        for pattern in issuer_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                structured.append(f"Issuer: {match.group(1).strip()}")
                break

    # Extract potential dates (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, etc.)
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
    ]
    for line in lines:
        for pattern in date_patterns:
            match = re.search(pattern, line)
            if match:
                structured.append(f"Date: {match.group(0)}")
                break

    # Extract certificate name (lines with "certificate", "cert", "completion", etc.)
    cert_patterns = [
        r'(.+certificate)',
        r'(.+certification)',
        r'(.+completion)',
    ]
    for line in lines:
        for pattern in cert_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                structured.append(f"Certificate Name: {match.group(1).strip()}")
                break

    # Add remaining text as body
    structured.append("\n--- Certificate Content ---")
    structured.append(raw_text)

    return '\n'.join(structured)


def ocr_pdf(pdf_path: str) -> str:
    """Extract text from image-only PDF using advanced OCR with structure normalization."""
    doc = fitz.open(pdf_path)
    text = ""

    for page_num, page in enumerate(doc):
        # Try multiple OCR strategies
        page_texts = []

        # Strategy 1: 300 DPI, psm6
        mat = fitz.Matrix(300/72, 300/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        page_text = pytesseract.image_to_string(img, config='--psm 6 -c preserve_interword_spaces=1')
        page_texts.append(("300dpi_psm6", page_text))

        # Strategy 2: 400 DPI, psm6
        mat = fitz.Matrix(400/72, 400/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        page_text = pytesseract.image_to_string(img, config='--psm 6 -c preserve_interword_spaces=1')
        page_texts.append(("400dpi_psm6", page_text))

        # Strategy 3: 400 DPI, psm11 (sparse text)
        mat = fitz.Matrix(400/72, 400/72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        page_text = pytesseract.image_to_string(img, config='--psm 11 -c preserve_interword_spaces=1')
        page_texts.append(("400dpi_psm11", page_text))

        # Select best result (longest non-empty text)
        best_strategy, best_text = max(page_texts, key=lambda x: len(x[1].strip()))
        text += f"\n--- Page {page_num + 1} ({best_strategy}) ---\n{best_text}\n"

    doc.close()

    # Apply structure normalization
    return normalize_certificate(text)

def main():
    output_dir = Path("data/raw/ocr_extracted")
    output_dir.mkdir(exist_ok=True)

    print("\n=== OCR FOR IMAGE-ONLY CERTIFICATE PDFs ===\n")

    for pdf_path in CERTIFICATE_PDFS:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"SKIP: {pdf_path} not found")
            continue

        print(f"Processing: {pdf_file.name}")

        try:
            text = ocr_pdf(str(pdf_file))

            # Save extracted text to sidecar .txt file
            txt_path = output_dir / f"{pdf_file.stem}_ocr.txt"
            txt_path.write_text(text, encoding="utf-8")

            print(f"  Extracted {len(text)} characters")
            print(f"  Saved to: {txt_path}")
            print(f"  Preview: {text[:200]}...")
            print()

        except Exception as e:
            print(f"  ERROR: {e}")
            print()

    print("=== OCR COMPLETE ===")

if __name__ == "__main__":
    main()
