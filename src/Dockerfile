# ──────────────────────────────────────────────────────────────
#  FraudShield — Production Dockerfile (Backend API)
#  Build:  docker build -t fraudshield-api -f src/Dockerfile .
#  Run:    docker run -p 8000:8000 --env-file .env fraudshield-api
# ──────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Install system dependencies for psycopg2 and bcrypt ──
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy application source and model artifacts ──
COPY src/ ./src/
COPY models/ ./models/

# ── Expose the API port ──
EXPOSE 8000

# ── Launch with uvicorn (production workers) ──
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
