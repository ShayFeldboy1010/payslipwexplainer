import importlib
import os
import sys

import fitz
from fastapi.testclient import TestClient


def create_pdf_bytes(text: str) -> bytes:
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), text)
        return doc.tobytes()


def test_analyze_and_ask(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    backend = importlib.import_module("backend")
    client = TestClient(backend.app)

    captured = {}

    class DummyClient:
        class chat:
            class completions:
                @staticmethod
                def create(model, messages, stream=False, timeout=60):
                    captured["messages"] = messages
                    class Res:
                        choices = [type("Choice", (), {"message": type("Msg", (), {"content": "answer"})()})]
                    return Res()

    import openai
    monkeypatch.setattr(openai, "OpenAI", lambda *a, **k: DummyClient())

    pdf_bytes = create_pdf_bytes("Gross 10000")
    response = client.post(
        "/analyze-payslip",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "payslip_id" in data

    ask_resp = client.post(
        "/ask",
        json={"question": "?", "payslip_id": data["payslip_id"]},
    )
    assert ask_resp.status_code == 200
    ask_data = ask_resp.json()
    assert ask_data["answer"] == "answer"
    assert "Gross 10000" in captured["messages"][1]["content"]
