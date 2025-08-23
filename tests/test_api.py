import os
import sys

# Ensure the project ``src`` directory is on the path for absolute imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_upload_and_ask() -> None:
    data = open("tests/data/sample_payslip.txt", "rb").read()
    resp = client.post("/api/upload", files={"file": ("sample_payslip.txt", data)})
    slip_id = resp.json()["slip_id"]
    resp = client.post(
        "/api/ask", json={"slip_id": slip_id, "question": "Gross?"}
    )
    assert resp.json()["answer"] == "10000"
