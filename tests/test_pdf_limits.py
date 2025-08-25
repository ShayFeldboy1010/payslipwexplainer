import importlib
import fitz


def create_multi_page_pdf(texts):
    doc = fitz.open()
    for txt in texts:
        page = doc.new_page()
        page.insert_text((72, 72), txt)
    return doc.tobytes()


def test_respects_max_pages(monkeypatch):
    monkeypatch.setenv("MAX_PAGES", "2")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    backend = importlib.reload(importlib.import_module("backend"))
    pdf_bytes = create_multi_page_pdf(["one", "two", "three"])
    text, ocr_used, _ = backend.extract_text_from_pdf(pdf_bytes)
    assert "one" in text and "two" in text
    assert "three" not in text
    assert ocr_used == 0
