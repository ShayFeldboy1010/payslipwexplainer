"""OCR implementation using Google's Gemini API via the ``google-generativeai``
package.

The function performs simple rotation handling (0/90/180/270 degrees) and
returns the longest text extracted.  Basic retry logic is implemented to cope
with transient API failures.
"""

from __future__ import annotations

import io
import logging
import os
import time
from typing import Iterable

from PIL import Image
import types

try:  # pragma: no cover - library may not be installed in some envs
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - handled gracefully
    genai = types.SimpleNamespace()  # type: ignore

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_ROTATIONS: Iterable[int] = (0, 90, 180, 270)


def _get_model() -> genai.GenerativeModel:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def _call_model(model: genai.GenerativeModel, img_bytes: bytes) -> str:
    """Call Gemini and return extracted text."""
    result = model.generate_content([
        {
            "mime_type": "image/png",
            "data": img_bytes,
        },
        "Extract all text from this image and return it.",
    ])
    try:
        return (
            result.candidates[0]
            .content.parts[0]
            .text.strip()
        )
    except Exception:
        return ""


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Extract text from *image_bytes* using Gemini."""
    model = _get_model()
    img = Image.open(io.BytesIO(image_bytes))
    best = ""
    for angle in _ROTATIONS:
        rotated = img.rotate(angle, expand=True) if angle else img
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        txt = ""
        for attempt in range(3):
            try:
                txt = _call_model(model, buf.getvalue())
                break
            except Exception as exc:
                if attempt == 2:
                    logging.exception("Gemini OCR request failed")
                    raise RuntimeError("Gemini OCR request failed") from exc
                wait = 2 ** attempt
                logging.warning("Gemini OCR error, retrying in %s s", wait)
                time.sleep(wait)
        if len(txt) > len(best):
            best = txt
        if len(best) > 20:
            break
    return best
