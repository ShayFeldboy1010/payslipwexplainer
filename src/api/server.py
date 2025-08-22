"""Very small HTTP API using the standard library."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from ingest import extract_text
from parser import parse_fields
from kb import KnowledgeBase

KB = KnowledgeBase()

class PayslipHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        if self.path == "/api/upload":
            slip_id = str(len(KB.store) + 1)
            text = extract_text(body)
            KB.add(slip_id, text)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"slip_id": slip_id}).encode())
        elif self.path == "/api/ask":
            data = json.loads(body.decode())
            slip_id = data.get("slip_id")
            question = data.get("question", "")
            text = KB.get(slip_id)
            fields = parse_fields(text)
            answer = ""
            if "gross" in question.lower():
                answer = str(fields.get("gross_salary", ""))
            elif "net" in question.lower():
                answer = str(fields.get("net_salary", ""))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"answer": answer, "sources": [{"slip_id": slip_id}]}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def run(port: int = 8000) -> None:
    """Run the HTTP server."""
    server = HTTPServer(("", port), PayslipHandler)
    server.serve_forever()

if __name__ == "__main__":
    run()
