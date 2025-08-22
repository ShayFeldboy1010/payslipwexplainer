"""Simple text extractor placeholder."""

def extract_text(data: bytes) -> str:
    """Return UTF-8 decoded text from bytes.

    This is a placeholder for actual PDF/OCR processing.
    """
    try:
        return data.decode("utf-8")
    except Exception:
        return ""
