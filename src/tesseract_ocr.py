"""Local OCR using Tesseract.

This module provides a drop-in replacement for Gemini OCR using the
`pytesseract` package.  It performs basic rotation handling similar to the
Gemini implementation: the image is rotated in 90-degree increments and the
longest result is returned.
"""

from __future__ import annotations

import io
from typing import Iterable

from PIL import Image

try:  # pragma: no cover - exercised in tests if available
    import pytesseract
except Exception:  # pragma: no cover - defensive: pytesseract not installed
    pytesseract = None  # type: ignore


_ROTATIONS: Iterable[int] = (0, 90, 180, 270)


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Return text extracted from *image_bytes* using Tesseract.

    The function attempts several rotations and returns the longest string.
    A :class:`RuntimeError` is raised if ``pytesseract`` or the ``tesseract``
    binary is not available.
    """
    if pytesseract is None or not pytesseract.get_tesseract_version():
        raise RuntimeError("Tesseract is not installed")

    image = Image.open(io.BytesIO(image_bytes))
    best = ""
    for angle in _ROTATIONS:
        rotated = image.rotate(angle, expand=True)
        text = pytesseract.image_to_string(rotated)
        if len(text) > len(best):
            best = text
        if len(best.strip()) > 20:
            break
    return best.strip()
