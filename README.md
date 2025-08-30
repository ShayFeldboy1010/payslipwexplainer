# Payslip Analyzer

A FastAPI-based service for analyzing Hebrew payslips with optional OCR and a simple HTML frontend.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export OPENAI_API_KEY=your_key_here  # if needed by your handlers
# Optional: set to use Google Gemini for OCR; otherwise Tesseract is used
export GOOGLE_API_KEY=your_google_api_key
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
- OCR support: optionally add `GOOGLE_API_KEY` for Gemini OCR; otherwise ensure
  the `tesseract` binary is installed on the host

## Testing

Run the unit tests with:

```bash
pytest
```

### OCR on Render
This app uses Google's Gemini API for scanned PDFs/images when a key is
provided.  Without a key it falls back to the local Tesseract engine.  Ensure
either the `GOOGLE_API_KEY` environment variable is set or `tesseract` is
installed on the host.
