import io
import importlib
import os

from PIL import Image, ImageDraw


def create_scanned_pdf(text: str) -> bytes:
    """Create a one-page scanned-style PDF with the given text."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 80), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def test_ocr_budget_retry(monkeypatch):
    """If OCR budget is zero, extractor should retry remaining pages."""
    monkeypatch.setenv("MAX_OCR_PAGES", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    backend = importlib.reload(importlib.import_module("backend"))

    pdf_bytes = create_scanned_pdf("Budget Test")

    # Pretend OCR always succeeds
    monkeypatch.setattr(backend, "_ocr_bytes", lambda _: "Budget Test")

    text, pages_used, _ = backend.extract_text_from_pdf(pdf_bytes)

    assert "Budget Test" in text
    assert pages_used == 1

