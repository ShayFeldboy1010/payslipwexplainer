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


def test_analyze_payslip_pdf_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    backend = importlib.import_module("backend")
    monkeypatch.setattr(backend, "explain_payslip_with_knowledge", lambda text, client: "analysis")
    client = TestClient(backend.app)
    pdf_bytes = create_pdf_bytes("Gross 10000")
    response = client.post("/analyze-payslip", files={"file": ("test.pdf", pdf_bytes, "application/pdf")})
    assert response.status_code == 200
    data = response.json()
    assert "Gross 10000" in data["extracted_text"]
    assert data["analysis"] == "analysis"
