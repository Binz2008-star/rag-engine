# Shared Document Corpus Configuration

## RAG System Corpus Location
The RAG system uses documents from: `data/raw/`

## Current ECO Technology Documents
- ECO Technology Environmental Protection Services L.L.C..md
- ECO_Agent_Training_Document.md
- ECO_Company_Profile.pdf
- ECO_Operational_Track_Record.md
- ECO_Technology_Company_Profile_Tier1.pdf
- eco_profile.pdf
- ecotech_company_profile.html

## Robin AI Integration
Robin AI agent will query the RAG service which retrieves from this corpus. No additional configuration needed - the RAG service automatically loads from `data/raw/`.

## Adding New Documents
To add new ECO Technology documents for both systems:
1. Place file in `data/raw/` directory
2. Rebuild RAG index: `python scripts/build_indexes.py`
3. RAG service will automatically use updated index on next query

## Document Types Supported
- PDF (.pdf)
- Markdown (.md)
- HTML (.html)
- DOCX (.docx)
- PPTX (.pptx) with structured slide extraction
- Image-only PDFs with OCR (certificates)
