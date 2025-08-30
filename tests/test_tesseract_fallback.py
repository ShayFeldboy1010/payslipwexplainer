import io
import os
import shutil
import sys

import pytest
from PIL import Image, ImageDraw

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
import ocr

pytesseract = pytest.importorskip("pytesseract")
if shutil.which("tesseract") is None:  # pragma: no cover - skip when not installed
    pytest.skip("tesseract binary not installed", allow_module_level=True)


def test_tesseract_basic():
    img = Image.new("RGB", (100, 40), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Hello", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    text = ocr.ocr_image_bytes(buf.getvalue())
    assert "Hello" in text
