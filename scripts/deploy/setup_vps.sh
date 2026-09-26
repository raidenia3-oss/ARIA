#!/usr/bin/env bash
# =============================================================================
# AURA Backend – Setup Automático para Oracle Cloud VPS (Ubuntu 22.04+)
# =============================================================================
# Uso:
#   chmod +x scripts/deploy/setup_vps.sh
#   sudo ./scripts/deploy/setup_vps.sh
# =============================================================================
# Este script:
#   1. Actualiza el sistema
#   2. Instala Docker + Docker Compose
#   3. Abre el puerto 8000 en ufw/iptables
#   4. Clona el repositorio, construye la imagen y levanta el contenedor
# =============================================================================

set -euo pipefail

# ── Colores para output ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${CYAN}[AURA]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Verificar que se ejecuta como root ──────────────────────────────
if [ "$EUID" -ne 0 ]; then
  fail "Este script debe ejecutarse como root (sudo)."
fi

# ── Configuración ───────────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/raidenia3-oss/AURA-server.01.git}"
BRANCH="${BRANCH:-main}"
AURA_PORT="${AURA_PORT:-8000}"
INSTALL_DIR="${INSTALL_DIR:-/opt/aura}"
CONTAINER_NAME="${CONTAINER_NAME:-aura-backend}"
IMAGE_NAME="${IMAGE_NAME:-aura-backend}"

# ── 1. Actualizar sistema ───────────────────────────────────────────
log "1/6 Actualizando paquetes del sistema..."
apt-get update -y && apt-get upgrade -y
ok "Sistema actualizado."

# ── 2. Instalar Docker ──────────────────────────────────────────────
log "2/6 Instalando Docker..."
if ! command -v docker &> /dev/null; then
  # Instalar dependencias
  apt-get install -y \
    ca-certificates curl gnupg lsb-release

  # Agregar repositorio oficial de Docker
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  ok "Docker instalado correctamente."
else
  ok "Docker ya está instalado."
fi

# ── 3. Abrir puerto 8000 en firewall ────────────────────────────────
log "3/6 Abriendo puerto ${AURA_PORT} en el firewall..."

# Intentar con ufw primero
if command -v ufw &> /dev/null; then
  ufw allow "${AURA_PORT}/tcp" 2>/dev/null || true
  ufw reload 2>/dev/null || true
  ok "Puerto ${AURA_PORT}/tcp abierto en ufw."
fi

# También agregar regla iptables por si acaso (Oracle Cloud bloquea por defecto)
iptables -C INPUT -p tcp --dport "${AURA_PORT}" -j ACCEPT 2>/dev/null || {
  iptables -A INPUT -p tcp --dport "${AURA_PORT}" -j ACCEPT
  # Persistente (netfilter-persistent)
  if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save 2>/dev/null || true
  fi
  ok "Regla iptables para puerto ${AURA_PORT} agregada."
}

# ── 4. Clonar repositorio ───────────────────────────────────────────
log "4/6 Clonando repositorio AURA..."

# Crear directorio si no existe
mkdir -p "$(dirname "${INSTALL_DIR}")"

if [ -d "${INSTALL_DIR}/.git" ]; then
  warn "El directorio ${INSTALL_DIR} ya existe. Actualizando..."
  cd "${INSTALL_DIR}"
  git fetch origin
  git reset --hard "origin/${BRANCH}"
else
  # Respaldo si hay algo en el path
  if [ -d "${INSTALL_DIR}" ]; then
    mv "${INSTALL_DIR}" "${INSTALL_DIR}.bak.$(date +%s)"
  fi
  git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"
ok "Repositorio clonado en ${INSTALL_DIR}."

# ── 5. Construir imagen Docker ──────────────────────────────────────
log "5/6 Construyendo imagen Docker de AURA..."
docker build -t "${IMAGE_NAME}" -f config/backend.Dockerfile .
ok "Imagen Docker construida: ${IMAGE_NAME}"

# ── 6. Detener contenedor anterior y levantar el nuevo ──────────────
log "6/6 Iniciando contenedor AURA..."

# Detener y eliminar contenedor anterior si existe
docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm "${CONTAINER_NAME}" 2>/dev/null || true

# Ejecutar contenedor en segundo plano con restart automático
docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  -p "${AURA_PORT}:${AURA_PORT}" \
  -e JWT_SECRET_ADMIN="${JWT_SECRET_ADMIN:-change_this_secret_in_prod}" \
  "${IMAGE_NAME}"

ok "Contenedor AURA iniciado en puerto ${AURA_PORT}."

# ── Verificar ───────────────────────────────────────────────────────
log "Verificando que el servidor responda..."
sleep 3
HEALTH_URL="http://localhost:${AURA_PORT}/health"
if curl -sf "${HEALTH_URL}" > /dev/null 2>&1; then
  ok "AURA Backend respondiendo correctamente en ${HEALTH_URL}"
else
  warn "El servidor parece no responder aún. Verifica los logs con:"
  echo "  docker logs -f ${CONTAINER_NAME}"
fi

# ── Resumen ─────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    AURA — Despliegue Completado             ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  URL local:    http://localhost:${AURA_PORT}                       ║"
echo "║  Health check: http://localhost:${AURA_PORT}/health               ║"
echo "║  Contenedor:   ${CONTAINER_NAME}                                   ║"
echo "║  Directorio:   ${INSTALL_DIR}                                       ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Comandos útiles:                                           ║"
echo "║  docker logs -f ${CONTAINER_NAME}    # Ver logs en vivo     ║"
echo "║  docker restart ${CONTAINER_NAME}    # Reiniciar servidor   ║"
echo "║  docker stop ${CONTAINER_NAME}       # Detener servidor     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""