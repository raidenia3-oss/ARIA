#!/usr/bin/env bash
set -euo pipefail

# AURA - Setup rápido para VPS Linux
# Uso: bash setup.sh [dominio]
# Si no pasas dominio, se usará el hostname del servidor.

DOMINIO="${1:-$(hostname -f)}"
echo "[INFO] Dominio detectado: ${DOMINIO}"

# 1) Verificar Docker
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] Docker no está instalado. Instálalo antes de continuar."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] Docker Compose (plugin) no está disponible."
  exit 1
fi

# 2) Directorios de persistencia
BASE_DIR="/opt/aura"
mkdir -p "${BASE_DIR}/data/chromadb" "${BASE_DIR}/data/sqlite"
chmod 777 "${BASE_DIR}/data/chromadb" "${BASE_DIR}/data/sqlite"

# 3) Variables de entorno por defecto
if [ ! -f "${BASE_DIR}/.env" ]; then
  cp .env.example "${BASE_DIR}/.env" 2>/dev/null || true
fi

# 4) Levantar stack en modo producción
docker compose up -d --build

echo "[OK] AURA debería estar corriendo en http://${DOMINIO}"
echo "     API:  http://${DOMINIO}/api/"
echo "     Front: http://${DOMINIO}/"
