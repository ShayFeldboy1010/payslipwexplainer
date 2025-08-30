"""Fast PDF/text extraction with optional OCR.

This module exposes :func:`extract_text` which accepts either raw PDF bytes or
plain UTF-8 encoded text.  For PDFs we rely on PyMuPDF to extract any embedded
text layer and fall back to sending page images to the OCR backend (Gemini or
Tesseract) when required.  Only pages that genuinely require OCR are processed
and the overall run time is bounded by a simple timeout.

The end result: even large or scanned payslips are parsed quickly without
requiring external dependencies when a Gemini key is available or falling back
to local Tesseract otherwise.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List

import fitz  # PyMuPDF
from ocr import ocr_image_bytes

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration knobs.  They keep the extractor responsive and can be tuned via
# environment variables.
# ---------------------------------------------------------------------------
MAX_TOTAL_SECONDS = float(os.getenv("MAX_TOTAL_SECONDS", "30"))


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract text from *pdf_bytes* using OCR for image-only pages."""

    start = time.perf_counter()
    page_texts: List[str] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            # honour a crude timeout to avoid stalling on huge files
            if time.perf_counter() - start > MAX_TOTAL_SECONDS:
                log.warning("PDF parse timeout at page %s", index)
                break

            # First attempt fast text extraction
            text = (page.get_text("text") or "").strip()
            if text:
                page_texts.append(text)
                continue

            # No text layer – fall back to OCR
            try:
                pix = page.get_pixmap()
                page_texts.append(ocr_image_bytes(pix.tobytes("png")))
            except Exception as exc:  # pragma: no cover - defensive programming
                log.warning("OCR failed for page %s: %s", index, exc)
                page_texts.append("")

    return "\n\n".join(t for t in page_texts if t)


def extract_text(data: bytes) -> str:
    """Return extracted text from *data*.

    ``data`` may represent a binary PDF or a plain UTF-8 text file.  The
    function auto-detects the format and chooses the fastest extraction
    strategy available.
    """

    # Quick check for PDF magic header
    if data.lstrip().startswith(b"%PDF"):
        try:
            return _extract_pdf(data)
        except Exception as exc:  # pragma: no cover - robustness
            log.warning("PDF extraction failed: %s", exc)

    # Fall back to decoding as UTF-8 text
    try:
        return data.decode("utf-8")
    except Exception:
        return ""

