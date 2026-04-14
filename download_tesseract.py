"""Download Tesseract OCR portable version."""

import requests
from pathlib import Path
import zipfile
import sys

# Try multiple sources
URLS = [
    "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-portable-5.5.0.20241111.zip",
    "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20231214/tesseract-ocr-w64-portable-5.4.0.20231214.zip",
]

TARGET_DIR = Path("D:/tools/tesseract")
DOWNLOAD_PATH = Path("D:/tools/tesseract_download.zip")

def download_file(url: str, path: Path) -> bool:
    """Download file with progress."""
    print(f"Trying: {url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=120, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        if total_size < 1000000:  # Less than 1MB is probably an error
            print(f"  File too small ({total_size} bytes), skipping")
            return False
            
        print(f"  Downloading {total_size / 1024 / 1024:.1f} MB...")
        
        downloaded = 0
        with open(path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) < 8192:  # Update every ~1MB
                            print(f"  {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB)")
        
        print(f"  Downloaded: {downloaded / 1024 / 1024:.1f} MB")
        return True
        
    except Exception as e:
        print(f"  Failed: {e}")
        return False

def extract_and_setup():
    """Extract and setup Tesseract."""
    print(f"\nExtracting to {TARGET_DIR}...")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(DOWNLOAD_PATH, 'r') as zip_ref:
        zip_ref.extractall(TARGET_DIR)
    
    # Find tesseract.exe
    tesseract_exe = list(TARGET_DIR.rglob("tesseract.exe"))
    if tesseract_exe:
        exe_path = tesseract_exe[0]
        print(f"Found: {exe_path}")
        
        # Create a small test script
        test_script = Path("d:/AI/assistant/test_tesseract.py")
        test_script.write_text(f'''import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"{exe_path}"
print("Version:", pytesseract.get_tesseract_version())
''')
        print(f"\nTest script created: {test_script}")
        print("Run: python test_tesseract.py")
    else:
        print("ERROR: tesseract.exe not found in extracted files")
        print("Contents:", list(TARGET_DIR.rglob("*"))[:20])

def main():
    TARGET_DIR.parent.mkdir(parents=True, exist_ok=True)
    
    for url in URLS:
        if download_file(url, DOWNLOAD_PATH):
            extract_and_setup()
            print("\n✓ Tesseract installed successfully!")
            return 0
    
    print("\n✗ All download sources failed.")
    print("\nManual install:")
    print("1. Download from: https://github.com/UB-Mannheim/tesseract/releases")
    print("2. Extract to: D:\\tools\\tesseract")
    print("3. Find tesseract.exe and update the path in rag_optimized.py")
    return 1

if __name__ == "__main__":
    sys.exit(main())
