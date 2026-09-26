# AURA Backend — Production Dockerfile (Python 3.11-slim)
# Cloud-ready: Render (Web Service) / Oracle Cloud VPS.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------------------------------------------------------------- #
# Builder stage: install dependencies into a virtualenv
# ---------------------------------------------------------------- #
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# ---------------------------------------------------------------- #
# Final stage: minimal runtime image
# ---------------------------------------------------------------- #
FROM base AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the backend source (package: ame_backend.src.main:app)
COPY ame_backend ./ame_backend

# Copy the dashboard served at /dashboard
COPY dashboard_local.html ./dashboard_local.html

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "ame_backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
