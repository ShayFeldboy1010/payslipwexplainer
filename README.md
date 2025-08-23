# Payslip Analyzer

A FastAPI-based service for analyzing Hebrew payslips with optional OCR and a simple HTML frontend.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional (for OCR on macOS, e.g. with Homebrew):
# brew install tesseract

export OPENAI_API_KEY=your_key_here  # if needed by your handlers
uvicorn backend:app --reload --port 8000
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/healthz  # -> {"status":"ok"}
open http://127.0.0.1:8000/
```

## Render deploy checklist

- Service type: **Web Service (Python)**
- `buildCommand`: `pip install -r requirements.txt`
- `startCommand`: `uvicorn backend:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath`: `/healthz`
- Env var: add `OPENAI_API_KEY` (sync: off, paste your key)
- OCR support: include `apt.txt` with `tesseract-ocr`

## Testing

Run the unit tests with:

```bash
pytest
```

### OCR on Render
This app uses Tesseract via `pytesseract` for scanned PDFs/images.
Render installs it from `apt.txt` (tesseract-ocr, -eng, -heb).  
If OCR is missing, scanned files will fail with 400 and a clear message.
