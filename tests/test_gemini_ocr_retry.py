import io
import importlib

from PIL import Image
import requests


def test_retry_on_timeout(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    gemini = importlib.reload(importlib.import_module("src.gemini_ocr"))

    calls = {"n": 0}
    expected = "X" * 25

    def fake_post(url, json, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.Timeout()
        class Resp:
            def raise_for_status(self):
                pass
            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": expected}]}}]}
        return Resp()

    monkeypatch.setattr(gemini.requests, "post", fake_post)

    img = Image.new("RGB", (50, 50), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    text = gemini.ocr_image_bytes(buf.getvalue())

    assert text == expected
    assert calls["n"] == 2
