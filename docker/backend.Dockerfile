# Backend AURA - Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ame_backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ame_backend /app/ame_backend

RUN useradd -m -u 1000 aura && \
    mkdir -p /app/models /app/fine-tuned-ame /app/training/data /app/logs && \
    chown -R aura:aura /app

USER aura

EXPOSE 8000

CMD ["uvicorn", "ame_backend.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
