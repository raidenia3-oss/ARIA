# =============================================
# AURA Backend - Producción Docker
# =============================================
FROM python:3.11-slim AS builder

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema primero (más rápido por capas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar caché de capas
COPY requirements.txt ./

# Instalar dependencias Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Etapa final - imagen mínima
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH"

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copiar dependencias instaladas desde builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código de la aplicación
COPY aura_api.py ./
COPY AURA_Core/ ./AURA_Core/
COPY core/ ./core/
COPY Shadow-Core/ ./Shadow-Core/
COPY AME_Core/ ./AME_Core/
COPY venice_modules/ ./venice_modules/
COPY aura_automation/ ./aura_automation/
COPY AME_Agent/ ./AME_Agent/
COPY nodes_config.json ./
COPY .env ./

# Cambiar ownership a usuario no-root
RUN chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Exponer puerto de la API
EXPOSE 8000

# Healthcheck para verificar que la API responde
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Comando de inicio
CMD ["uvicorn", "aura_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
