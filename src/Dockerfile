# ──────────────────────────────────────────────────────────────
#  FraudShield — Production Dockerfile (Backend API)
#  Build:  docker build -t fraudshield-api -f src/Dockerfile .
#  Run:    docker run -p 8000:8000 --env-file .env fraudshield-api
# ──────────────────────────────────────────────────────────────

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    FORWARDED_ALLOW_IPS="*"

WORKDIR /app

# ── Python dependencies (all pure wheels; no compiler or libpq needed) ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application source and model artifacts ──
COPY src/ ./src/
COPY models/ ./models/

# ── Run unprivileged ──
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,sys,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)" || exit 1

# WEB_CONCURRENCY sets the worker count (default 1; each worker loads the model into memory).
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
