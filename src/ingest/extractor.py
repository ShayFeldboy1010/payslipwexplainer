"""Fast PDF/text extraction leveraging PyMuPDF's native OCR.

This module exposes :func:`extract_text` which accepts either raw PDF bytes or
plain UTF-8 encoded text.  For PDFs we rely on ``page.get_textpage_ocr`` – a
PyMuPDF helper that combines regular text extraction with on-demand OCR of
images.  This dramatically cuts processing time compared to the previous
pipeline which rasterised pages and invoked ``pytesseract`` manually.  Only
pages that genuinely require OCR are processed at a configurable DPI and the
overall run time is bounded by a simple timeout.

The end result: even large or scanned payslips are parsed in a few seconds
without external services or heavyweight temporary files.
"""

from __future__ import annotations

import logging
import os
import time
from typing import List

import fitz  # PyMuPDF

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration knobs.  They keep the extractor responsive and can be tuned via
# environment variables.
# ---------------------------------------------------------------------------
OCR_DPI = int(os.getenv("OCR_DPI", "150"))  # resolution used for OCR fallback
MAX_TOTAL_SECONDS = float(os.getenv("MAX_TOTAL_SECONDS", "30"))
OCR_LANG = os.getenv("OCR_LANG", "heb+eng")


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract text from *pdf_bytes* using PyMuPDF's integrated OCR."""

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

            # No text layer – fall back to MuPDF's OCR helper.  This call uses
            # the Tesseract engine internally but avoids intermediate PNGs and
            # subprocess management, yielding much faster results.
            try:
                tp = page.get_textpage_ocr(dpi=OCR_DPI, full=True, language=OCR_LANG)
                page_texts.append((tp.extract_text() or "").strip())
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

