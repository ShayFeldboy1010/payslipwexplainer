"""Unified OCR interface.

The project historically relied on Google's Gemini API for optical character
recognition.  This module wraps the Gemini implementation and provides a
transparent fallback to the local Tesseract engine when a ``GOOGLE_API_KEY`` is
not configured or the remote call fails.  The goal is to keep the rest of the
codebase agnostic to the OCR backend while maximising reliability.
"""

from __future__ import annotations

import os
import shutil

try:  # package-relative import
    from .gemini_ocr import ocr_image_bytes as _gemini_ocr
except Exception:  # fallback when imported as a script
    from gemini_ocr import ocr_image_bytes as _gemini_ocr  # type: ignore

try:  # pragma: no cover - exercised in tests if available
    from .tesseract_ocr import ocr_image_bytes as _tesseract_ocr
except Exception:  # pragma: no cover - defensive: pytesseract missing
    try:
        from tesseract_ocr import ocr_image_bytes as _tesseract_ocr  # type: ignore
    except Exception:
        _tesseract_ocr = None  # type: ignore


def _tesseract_available() -> bool:
    return _tesseract_ocr is not None and shutil.which("tesseract") is not None


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Return text extracted from *image_bytes* using the best available OCR.

    Preference is given to the Gemini API when a ``GOOGLE_API_KEY`` environment
    variable is configured.  If Gemini fails or is unavailable, the function
    falls back to a local Tesseract OCR implementation (if installed).
    """

    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            return _gemini_ocr(image_bytes)
        except Exception:
            pass

    if _tesseract_available():
        return _tesseract_ocr(image_bytes)  # type: ignore[misc]

    raise RuntimeError("No OCR backend available")
