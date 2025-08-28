import base64
import io
import os
import logging

import requests
from PIL import Image

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY = os.getenv("GOOGLE_API_KEY")


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Extract text from *image_bytes* using Google's Gemini API.

    Performs basic rotation handling by trying 0/90/180/270 degrees and
    returning the longest result.
    """
    if not API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    img = Image.open(io.BytesIO(image_bytes))
    best = ""
    for angle in (0, 90, 180, 270):
        rotated = img.rotate(angle, expand=True) if angle else img
        buf = io.BytesIO()
        rotated.save(buf, format="PNG")
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(buf.getvalue()).decode("utf-8"),
                            }
                        },
                        {
                            "text": "Extract all text from this image and return it."
                        },
                    ]
                }
            ]
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
            f"?key={API_KEY}"
        )
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            txt = (
                resp.json()
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
        except Exception as exc:
            logging.exception("Gemini OCR request failed")
            raise RuntimeError("Gemini OCR request failed") from exc
        if len(txt) > len(best):
            best = txt
        if len(best) > 20:
            break
    return best
