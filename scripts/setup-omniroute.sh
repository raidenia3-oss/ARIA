#!/bin/bash

# AURA OS — Omniroute Setup Script
# Instala y configura Omniroute localmente

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     AURA OS — Omniroute Setup                                  ║"
echo "║     Install & Configure Multi-Provider AI Gateway               ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ═══════════════════════════════════════════════════════════════════════════
# 1. Verificar requisitos
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[1/5] Checking requirements...${NC}"

# Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2)${NC}"

# Docker (opcional pero recomendado)
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓ Docker installed${NC}"
    DOCKER_AVAILABLE=true
else
    echo -e "${YELLOW}⚠ Docker not found (install opcional)${NC}"
    DOCKER_AVAILABLE=false
fi

# Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}ERROR: Git not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Git${NC}"

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 2. Opción A: Docker (Recomendado)
# ═══════════════════════════════════════════════════════════════════════════

if [ "$DOCKER_AVAILABLE" = true ]; then
    echo -e "${YELLOW}[2/5] Setting up Omniroute with Docker...${NC}"

    mkdir -p omniroute-docker
    cd omniroute-docker

    cat > Dockerfile << 'EOF'
FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir omniroute

EXPOSE 8080

CMD ["omniroute", "start", "--host", "0.0.0.0", "--port", "8080"]
EOF

    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  omniroute:
    build: .
    ports:
      - "8080:8080"
    environment:
      - OMNIROUTE_ENV=production
    volumes:
      - ./config:/app/config
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
EOF

    echo -e "${GREEN}✓ Docker setup files created${NC}"
    echo ""
    echo "To start Omniroute with Docker:"
    echo "  cd omniroute-docker"
    echo "  docker-compose up -d"
    echo ""

    cd ..
else
    echo -e "${YELLOW}[2/5] Skipping Docker setup (not installed)${NC}"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 3. Opción B: Instalación local (pip)
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[3/5] Installing Omniroute locally...${NC}"

if [ ! -d "omniroute-venv" ]; then
    python3 -m venv omniroute-venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# shellcheck disable=SC1091
source omniroute-venv/bin/activate

pip install --upgrade pip setuptools wheel --quiet
pip install omniroute --quiet

echo -e "${GREEN}✓ Omniroute installed${NC}"

deactivate

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 4. Crear configuración
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[4/5] Creating configuration...${NC}"

mkdir -p omniroute-config

cat > omniroute-config/config.yaml << 'EOF'
server:
  host: 0.0.0.0
  port: 8080
  workers: 4
  timeout: 30

logging:
  level: INFO
  format: json

providers:
  # Omniroute descubrirá automáticamente todos los proveedores
  # Configura aquí los que quieras personalizar

  groq:
    enabled: true
    priority: high

  openrouter:
    enabled: true
    priority: high

  ollama:
    enabled: false  # Cambiar a true si tienes Ollama instalado
    host: http://localhost:11434

  local:
    enabled: false

cache:
  enabled: true
  ttl: 300  # 5 minutos

monitoring:
  enabled: true
  interval: 60  # 1 minuto
  health_check_timeout: 10
EOF

echo -e "${GREEN}✓ Configuration created at omniroute-config/config.yaml${NC}"

cat > omniroute-config/start-omniroute.sh << 'EOF'
#!/bin/bash

source ../omniroute-venv/bin/activate

# Opciones:
# Con configuración: omniroute start --config config.yaml
# Sin configuración: omniroute start

omniroute start --host 0.0.0.0 --port 8080
EOF

chmod +x omniroute-config/start-omniroute.sh

echo -e "${GREEN}✓ Startup script created at omniroute-config/start-omniroute.sh${NC}"

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# 5. Verificación
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}[5/5] Creating verification script...${NC}"

cat > test-omniroute.sh << 'EOF'
#!/bin/bash

# Test Omniroute connectivity

echo "Testing Omniroute connection..."
echo ""

# Health check
echo "[1] Health Check:"
curl -s http://localhost:8080/api/health | jq '.' 2>/dev/null || echo "Omniroute not responding"
echo ""

# List providers
echo "[2] Available Providers:"
curl -s http://localhost:8080/api/providers | jq '.providers | length' 2>/dev/null || echo "Error fetching providers"
echo ""

# Test chat
echo "[3] Test Chat (simple):"
curl -s -X POST http://localhost:8080/api/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hi"}],
    "temperature": 0.7,
    "max_tokens": 100
  }' | jq '.choices[0].message.content' 2>/dev/null || echo "Chat test failed"
EOF

chmod +x test-omniroute.sh

echo -e "${GREEN}✓ Test script created at ./test-omniroute.sh${NC}"

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗"
echo "║      ✅ Omniroute Setup Complete!                               ║"
echo "╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo "Next steps:"
echo ""

if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "Option 1: Run with Docker (RECOMMENDED)"
    echo "  cd omniroute-docker"
    echo "  docker-compose up -d"
    echo "  # Omniroute will start at http://localhost:8080"
    echo ""
fi

echo "Option 2: Run locally"
echo "  cd omniroute-config"
echo "  ./start-omniroute.sh"
echo "  # In another terminal:"
echo "  ../test-omniroute.sh"
echo ""

echo "Option 3: Quick test"
echo "  ./test-omniroute.sh"
echo ""

echo "Then, update AURA .env:"
echo "  OMNIROUTE_URL=http://localhost:8080"
echo ""

echo "And test AURA integration:"
echo "  curl http://localhost:8000/api/omniroute/health"
echo "  curl http://localhost:8000/api/providers"
echo "  curl -X POST http://localhost:8000/api/chat/omniroute \\"
echo "    -d '{\"message\": \"Hello\"}'"
echo ""
