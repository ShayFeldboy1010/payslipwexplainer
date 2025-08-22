# Payslip Analyzer

This repository contains a minimal skeleton for analysing payslip documents.
It demonstrates an ingestion pipeline, simple parsing, an in-memory knowledge
base and a tiny HTTP API.  The heavy-weight components described in the project
plan (OCR, embeddings, Groq integration and rich UI) are represented here as
placeholders so the structure can be exercised locally.

## Structure

```
src/
  ingest/     # PDF/image ingestion (placeholder)
  parser/     # extract fields from text
  kb/         # simple in-memory knowledge base
  llm/        # Groq client wrapper (placeholder)
  api/        # minimal HTTP server with two endpoints
```

## Runbook

1. Copy the environment template and add your Groq key if available:
   ```bash
   cp .env.example .env
   export GROQ_API_KEY=<key>
   ```
2. Run the API server:
   ```bash
   python -m api.server
   ```
3. Upload a payslip (here we just send plain text for demonstration):
   ```bash
   curl -X POST --data-binary @tests/data/sample_payslip.txt http://localhost:8000/api/upload
   ```
4. Ask a question about the uploaded slip:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"slip_id": "1", "question": "Gross?"}' \
     http://localhost:8000/api/ask
   ```

## Testing

Run the unit tests with:
```bash
pytest
```

## Validation checklist

- [ ] Text and scanned PDFs are processed (placeholder only).
- [x] Hebrew RTL text can be processed (not applicable in skeleton).
- [ ] Q&A uses Groq LLM with citations (placeholder only).
- [x] Unit tests pass.
