"""Quick script to check index metadata and certificate PDFs."""
import json
from pathlib import Path
from collections import Counter

meta_path = Path("storage/metadata.json")
if not meta_path.exists():
    print("No metadata.json found")
else:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    source_counts = Counter(m["source"] for m in meta)
    print(f"Total chunks: {len(meta)}")
    print(f"Unique sources: {len(source_counts)}")
    for s, c in sorted(source_counts.items()):
        print(f"  {s}: {c} chunks")

# Check raw files
raw_dir = Path("data/raw")
print(f"\nRaw files in {raw_dir}:")
for f in sorted(raw_dir.iterdir()):
    if f.is_file():
        print(f"  {f.name} ({f.stat().st_size} bytes)")

# Check certificate PDFs specifically
cert_files = [f for f in raw_dir.iterdir() if "certificate" in f.name.lower() or "cert" in f.name.lower()]
print(f"\nCertificate files: {len(cert_files)}")
for f in cert_files:
    print(f"  {f.name} ({f.stat().st_size} bytes)")
    if f.name.endswith(".pdf"):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(f))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            print(f"    Extracted text length: {len(text)} chars")
            if text.strip():
                print(f"    First 200 chars: {text.strip()[:200]}")
            else:
                print(f"    WARNING: No text extracted (image-only PDF?)")
        except ImportError:
            print("    PyMuPDF not available, trying pdfplumber...")
            try:
                import pdfplumber
                with pdfplumber.open(str(f)) as pdf:
                    text = ""
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            text += t
                    print(f"    Extracted text length: {len(text)} chars")
                    if text.strip():
                        print(f"    First 200 chars: {text.strip()[:200]}")
                    else:
                        print(f"    WARNING: No text extracted (image-only PDF?)")
            except ImportError:
                print("    No PDF library available")
