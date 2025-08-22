import json
import os
import sys
import threading
import time
import urllib.request

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from api import run

def start_server():
    thread = threading.Thread(target=run, kwargs={"port": 8001}, daemon=True)
    thread.start()
    time.sleep(0.2)

def test_upload_and_ask():
    start_server()
    data = open("tests/data/sample_payslip.txt", "rb").read()
    req = urllib.request.Request("http://localhost:8001/api/upload", data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        slip_id = json.load(resp)["slip_id"]
    payload = json.dumps({"slip_id": slip_id, "question": "Gross?"}).encode()
    req = urllib.request.Request(
        "http://localhost:8001/api/ask",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        answer = json.load(resp)
    assert answer["answer"] == "10000"
