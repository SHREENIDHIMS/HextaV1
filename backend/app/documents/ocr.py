"""Optional OCR module for scanned PDFs.

Uses Tesseract (tesseract-ocr) to extract text from image-based PDFs.
This is an optional dependency — not all documents need OCR.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from pdf2image import convert_from_path

    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.warning("tesseract / pdf2image not installed; OCR support disabled")


def ocr_pdf(pdf_path: str | Path) -> str:
    """Extract text from a scanned PDF using OCR.

    Returns empty string if OCR dependencies are not installed.
    """
    if not HAS_OCR:
        raise RuntimeError(
            "OCR requires pytesseract and pdf2image. "
            "Install with: pip install pytesseract pdf2image"
        )

    path = Path(pdf_path)
    images = convert_from_path(str(path))
    text_parts: list[str] = []
    for img in images:
        text_parts.append(pytesseract.image_to_string(img))
    return "\n".join(text_parts)