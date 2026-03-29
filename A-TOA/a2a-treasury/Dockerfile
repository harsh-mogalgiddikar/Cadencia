# ── Stage 1: Build ──────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000

# ── Development (hot-reload) ────────────────────────────────────
FROM base AS development
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production (gunicorn + uvicorn workers) ─────────────────────
FROM base AS production
RUN pip install gunicorn==21.2.0
RUN adduser --disabled-password --gecos "" appuser
USER appuser
CMD ["gunicorn", "api.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "120", "--keep-alive", "5"]
