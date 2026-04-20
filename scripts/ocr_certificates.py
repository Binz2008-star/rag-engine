"""OCR script for image-only certificate PDFs."""
import fitz
from pathlib import Path
import pytesseract
from PIL import Image
import io

# Image-only certificate PDFs
CERTIFICATE_PDFS = [
    "data/raw/Sellora_Process_Automation_Certificate.pdf",
    "data/raw/Sellora_WhatsApp_Operations_Certificate.pdf",
]

def ocr_pdf(pdf_path: str) -> str:
    """Extract text from image-only PDF using OCR."""
    doc = fitz.open(pdf_path)
    text = ""
    
    for page_num, page in enumerate(doc):
        # Render page as image
        pix = page.get_pixmap()
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        
        # OCR the image
        page_text = pytesseract.image_to_string(img)
        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
    
    doc.close()
    return text

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
