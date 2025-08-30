import io
import importlib
import os
import sys

from PIL import Image

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def test_retry_on_timeout(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    gemini = importlib.reload(importlib.import_module("src.gemini_ocr"))

    calls = {"n": 0}
    expected = "X" * 25

    class DummyModel:
        def generate_content(self, parts):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError()
            class Resp:
                def __init__(self, text):
                    self.candidates = [
                        type(
                            "C",
                            (),
                            {
                                "content": type(
                                    "Cont",
                                    (),
                                    {"parts": [type("P", (), {"text": text})()]},
                                )(),
                            },
                        )
                    ]

            return Resp(expected)

    monkeypatch.setattr(gemini.genai, "configure", lambda **_: None, raising=False)
    monkeypatch.setattr(gemini.genai, "GenerativeModel", lambda model: DummyModel(), raising=False)
    monkeypatch.setattr(gemini.time, "sleep", lambda _: None)

    img = Image.new("RGB", (50, 50), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    text = gemini.ocr_image_bytes(buf.getvalue())

    assert text == expected
    assert calls["n"] == 2
