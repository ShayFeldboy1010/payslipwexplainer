import os
import sys
import importlib
import fitz
from fastapi.testclient import TestClient


def create_pdf_bytes(text: str) -> bytes:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), text)
        return doc.tobytes()


def test_compare(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    sys.path.append(os.path.dirname(__file__) + "/..")
    backend = importlib.import_module("backend")
    client = TestClient(backend.app)

    captured = {}

    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(model, messages, temperature=0.3, max_tokens=4000):
                    captured["messages"] = messages
                    class Res:
                        choices = [type("Choice", (), {"message": type("Msg", (), {"content": "analysis"})()})]
                    return Res()

    monkeypatch.setattr(backend, "client", DummyClient())

    pdf1 = create_pdf_bytes("Gross 100")
    pdf2 = create_pdf_bytes("Gross 200")
    files = [
        ("files", ("a.pdf", pdf1, "application/pdf")),
        ("files", ("b.pdf", pdf2, "application/pdf")),
    ]
    resp = client.post("/compare-payslips", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 2
    assert len(data["payslips"]) == 2
    assert data["payslips"][0]["filename"] == "a.pdf"
    assert captured["messages"]

