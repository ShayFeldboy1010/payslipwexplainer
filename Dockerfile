# ---- Base ----
FROM python:3.11-slim

# Prevents Python from writing .pyc files and enables unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps: libs for PyMuPDF/Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# Workdir
WORKDIR /app

# Install Python deps first (better caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app files
COPY . /app

# Render provides $PORT; default fallback
ENV PORT=8000

# Healthcheck is served from backend.py (/healthz)
# Expose is just documentation; Render maps ports automatically
EXPOSE 8000

# Start the app
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
