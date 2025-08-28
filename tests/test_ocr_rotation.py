import io
import importlib
import os

from PIL import Image, ImageDraw
import pytest


def create_scanned_pdf(text: str, rotate: int = 0) -> bytes:
    """Create a one-page PDF from rendered text, optionally rotated."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), text, fill="black")
    if rotate:
        img = img.rotate(rotate, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def test_rotated_pdf_ocr(monkeypatch):
    """Ensure OCR can handle sideways scanned PDFs."""
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    backend = importlib.reload(importlib.import_module("backend"))

    if not backend.TESSERACT_AVAILABLE:
        pytest.skip("tesseract not available")

    pdf_bytes = create_scanned_pdf("Gross 12345", rotate=90)
    text, pages_used, _ = backend.extract_text_from_pdf(pdf_bytes)

    assert "Gross 12345" in text
    assert pages_used >= 1

