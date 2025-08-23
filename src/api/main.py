import logging
import os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from src.ingest import extract_text
from src.parser import parse_fields
from src.kb import KnowledgeBase

app = FastAPI(title="Payslip Analyzer")

origins = ["http://localhost", "http://localhost:3000", "http://localhost:8000"]
render_origin = os.environ.get("RENDER_EXTERNAL_URL")
if render_origin:
    origins.append(render_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

KB = KnowledgeBase()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

@app.on_event("startup")
async def startup_event() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "8000")
    logging.getLogger("uvicorn").info(f"Starting Payslip Analyzer on {host}:{port}")

@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_path = BASE_DIR / "frontend.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body><h1>Payslip Analyzer</h1></body></html>")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    slip_id = str(len(KB.store) + 1)
    text = extract_text(data)
    KB.add(slip_id, text)
    return {"slip_id": slip_id}

class AskRequest(BaseModel):
    slip_id: str
    question: str

@app.post("/api/ask")
async def ask(req: AskRequest) -> dict:
    text = KB.get(req.slip_id)
    if not text:
        raise HTTPException(status_code=404, detail="Unknown slip_id")
    fields = parse_fields(text)
    answer = ""
    if "gross" in req.question.lower():
        answer = str(fields.get("gross_salary", ""))
    elif "net" in req.question.lower():
        answer = str(fields.get("net_salary", ""))
    return {"answer": answer, "sources": [{"slip_id": req.slip_id}]}
