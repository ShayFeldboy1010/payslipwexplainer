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
from concurrent.futures import ThreadPoolExecutor, Future

import fitz  # PyMuPDF
from ocr import ocr_image_bytes

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration knobs.  They keep the extractor responsive and can be tuned via
# environment variables.
# ---------------------------------------------------------------------------
MAX_TOTAL_SECONDS = float(os.getenv("MAX_TOTAL_SECONDS", "20"))


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract text from *pdf_bytes* using OCR for image-only pages."""

    start = time.perf_counter()
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        texts: List[str] = [""] * doc.page_count
        ocr_jobs: List[tuple[int, Future[str]]] = []

        with ThreadPoolExecutor() as pool:
            for index, page in enumerate(doc):
                if time.perf_counter() - start > MAX_TOTAL_SECONDS:
                    log.warning("PDF parse timeout at page %s", index)
                    break

                text = (page.get_text("text") or "").strip()
                if text:
                    texts[index] = text
                    continue

                try:
                    pix = page.get_pixmap()
                    ocr_jobs.append((index, pool.submit(ocr_image_bytes, pix.tobytes("png"))))
                except Exception as exc:  # pragma: no cover - defensive programming
                    log.warning("OCR enqueue failed for page %s: %s", index, exc)

        for index, fut in ocr_jobs:
            remaining = MAX_TOTAL_SECONDS - (time.perf_counter() - start)
            if remaining <= 0:
                log.warning("OCR timeout while waiting for page %s", index)
                break
            try:
                texts[index] = fut.result(timeout=remaining)
            except Exception as exc:  # pragma: no cover - defensive programming
                log.warning("OCR failed for page %s: %s", index, exc)

    return "\n\n".join(t for t in texts if t)


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

