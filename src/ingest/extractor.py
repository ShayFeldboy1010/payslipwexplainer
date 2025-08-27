"""Efficient PDF/text extraction utilities.

This module exposes :func:`extract_text` which tries to return readable text from
either a binary PDF or a plain text file.  The previous implementation simply
decoded the bytes as UTF-8 which worked for ``.txt`` fixtures but failed for
real PDF uploads and required slow, external processing elsewhere.  The new
implementation uses PyMuPDF for direct text extraction and only falls back to
OCR when absolutely necessary.  Pages without embedded text are rasterised once
and processed concurrently with ``pytesseract``.  Small time/page budgets ensure
that even scanned payslips return results in a few seconds instead of minutes.
"""

from __future__ import annotations

import io
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image

try:  # Optional dependency: if missing we simply skip OCR fallback
    import pytesseract
except Exception:  # pragma: no cover - during tests we don't require OCR
    pytesseract = None

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration knobs.  These can be tuned via environment variables and keep
# the extractor responsive even on large or fully‑scanned PDFs.
# ---------------------------------------------------------------------------
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", "2"))
MAX_TOTAL_SECONDS = float(os.getenv("MAX_TOTAL_SECONDS", "30"))
OCR_SCALE = float(os.getenv("OCR_SCALE", "2.0"))
OCR_WORKERS = int(os.getenv("MAX_OCR_WORKERS", "4"))
OCR_CONFIG = "--oem 3 --psm 6"  # reasonable balance between speed/accuracy
_OCR_MATRIX = fitz.Matrix(OCR_SCALE, OCR_SCALE)


def _ocr_image(image_bytes: bytes) -> str:
    """Run Tesseract OCR on PNG bytes if available."""

    if pytesseract is None:  # OCR engine missing
        return ""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, config=OCR_CONFIG)
    except Exception:  # pragma: no cover - defensive programming
        return ""


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF, using selective OCR when necessary."""

    start = time.perf_counter()
    page_texts: List[str] = []
    ocr_jobs: Dict[int, bytes] = {}
    ocr_used = 0

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            if time.perf_counter() - start > MAX_TOTAL_SECONDS:
                log.warning("PDF parse timeout at page %s", index)
                break

            text = (page.get_text("text") or "").strip()
            if text:  # regular selectable text; quick path
                page_texts.append(text)
                continue

            if ocr_used >= MAX_OCR_PAGES:
                page_texts.append("")
                continue

            # Fallback to OCR: rasterise once, store bytes for later
            pix = page.get_pixmap(matrix=_OCR_MATRIX, alpha=False)
            ocr_jobs[index] = pix.tobytes("png")
            page_texts.append("")
            ocr_used += 1

    if ocr_jobs:
        with ThreadPoolExecutor(max_workers=min(len(ocr_jobs), OCR_WORKERS)) as ex:
            futures = {ex.submit(_ocr_image, b): i for i, b in ocr_jobs.items()}
            for fut in as_completed(futures):
                page_index = futures[fut]
                try:
                    page_texts[page_index] = fut.result().strip()
                except Exception:  # pragma: no cover - robustness
                    pass

    return "\n\n".join(t for t in page_texts if t)


def extract_text(data: bytes) -> str:
    """Return extracted text from *data*.

    ``data`` may represent a binary PDF or a plain UTF‑8 text file.  The
    function auto‑detects the format and uses the most efficient extraction
    strategy available.
    """

    # Fast path for PDFs detected by their magic header
    if data.lstrip().startswith(b"%PDF"):
        try:
            return _extract_pdf(data)
        except Exception as exc:
            log.warning("PDF extraction failed: %s", exc)

    # Fall back to simple UTF‑8 decode for text files
    try:
        return data.decode("utf-8")
    except Exception:
        return ""
