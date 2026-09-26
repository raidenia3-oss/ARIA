#!/bin/bash
# AURA OS Personalizada - Script de inicio
# Inicia todos los servicios de la distro personalizada

set -e

echo "╔════════════════════════════════════════════╗"
echo "║     AURA OS Personalizada - Starting...   ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# ============================================
# FASE 1: Verificar sistema
# ============================================
echo -e "${YELLOW}[1/6] Verificando sistema...${NC}"

if [ -f /etc/alpine-release ]; then
    echo -e "${GREEN}✓ Alpine Linux detectado${NC}"
else
    echo -e "${RED}✗ No se detectó Alpine Linux${NC}"
    exit 1
fi

# Verificar que estamos como root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}✗ Ejecutar como root${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Sistema OK${NC}"
echo ""

# ============================================
# FASE 2: Iniciar servicios base
# ============================================
echo -e "${YELLOW}[2/6] Iniciando servicios base...${NC}"

# Redis
if command -v redis-server &> /dev/null; then
    echo -e "${BLUE}Iniciando Redis...${NC}"
    redis-server --daemonize yes 2>/dev/null || true
    echo -e "${GREEN}✓ Redis iniciado${NC}"
fi

# PostgreSQL
if command -v pg_ctl &> /dev/null; then
    echo -e "${BLUE}Iniciando PostgreSQL...${NC}"
    su - postgres -c "pg_ctl -D /var/lib/postgresql/data start" 2>/dev/null || true
    echo -e "${GREEN}✓ PostgreSQL iniciado${NC}"
fi

echo ""

# ============================================
# FASE 3: Iniciar AURA Backend
# ============================================
echo -e "${YELLOW}[3/6] Iniciando AURA Backend...${NC}"

if [ -d /opt/aura/backend ]; then
    echo -e "${BLUE}Iniciando AURA Brain en puerto 8000...${NC}"
    
    # Activar venv si existe
    if [ -d /opt/aura/backend/venv ]; then
        source /opt/aura/backend/venv/bin/activate
    fi
    
    # Iniciar backend
    cd /opt/aura/backend
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    AURA_PID=$!
    
    echo -e "${GREEN}✓ AURA Brain iniciado (PID: $AURA_PID)${NC}"
    echo -e "${BLUE}Backend: http://localhost:8000${NC}"
    
    # Esperar a que inicie
    sleep 3
    
    # Verificar
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend respondiendo correctamente${NC}"
    else
        echo -e "${YELLOW}⚠ Backend no responde aún (puede tardar unos segundos)${NC}"
    fi
else
    echo -e "${RED}✗ Backend no encontrado en /opt/aura/backend${NC}"
    echo -e "${YELLOW}Ejecuta primero: sh /mnt/usb/aura-install/aura-installer.sh${NC}"
fi

echo ""

# ============================================
# FASE 4: Iniciar Hyprland
# ============================================
echo -e "${YELLOW}[4/6] Verificando Hyprland...${NC}"

if command -v Hyprland &> /dev/null; then
    echo -e "${GREEN}✓ Hyprland disponible${NC}"
    echo -e "${BLUE}Para iniciar: Hyprland${NC}"
else
    echo -e "${YELLOW}⚠ Hyprland no instalado (opcional)${NC}"
    echo -e "${YELLOW}Instalar con: apk add hyprland${NC}"
fi

echo ""

# ============================================
# FASE 5: Iniciar Dashboard Web
# ============================================
echo -e "${YELLOW}[5/6] Iniciando Dashboard Web...${NC}"

if [ -f /opt/aura/aura-dashboard.html ]; then
    echo -e "${BLUE}Iniciando servidor web en puerto 8080...${NC}"
    cd /opt/aura
    python3 -m http.server 8080 &
    DASHBOARD_PID=$!
    
    echo -e "${GREEN}✓ Dashboard iniciado (PID: $DASHBOARD_PID)${NC}"
    echo -e "${BLUE}Dashboard: http://localhost:8080/aura-dashboard.html${NC}"
else
    echo -e "${YELLOW}⚠ Dashboard no encontrado${NC}"
fi

echo ""

# ============================================
# FASE 6: Resumen
# ============================================
echo -e "${YELLOW}[6/6] Resumen${NC}"
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   AURA OS Personalizada - LISTA          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${PURPLE}Servicios:${NC}"
echo -e "  ${BLUE}AURA Backend:${NC}  http://localhost:8000"
echo -e "  ${BLUE}Health Check:${NC}  curl http://localhost:8000/health"
echo -e "  ${BLUE}Dashboard:${NC}     http://localhost:8080/aura-dashboard.html"
echo ""
echo -e "${PURPLE}CLI Tools:${NC}"
echo -e "  ${BLUE}aura-cli.sh:${NC}      Chat de texto con AURA"
echo -e "  ${BLUE}aura-voice.sh:${NC}    Chat con voz (espeak)"
echo -e "  ${BLUE}aura_cli.rb:${NC}      CLI en Ruby"
echo -e "  ${BLUE}custom_tools.rb:${NC}  Herramientas de seguridad"
echo -e "  ${BLUE}panel.sh:${NC}         Panel del sistema"
echo -e "  ${BLUE}wallpaper-rotator.sh:${NC} Slideshow de wallpapers"
echo ""
echo -e "${PURPLE}Comandos útiles:${NC}"
echo -e "  ${YELLOW}sh /root/aura-cli.sh${NC}"
echo -e "  ${YELLOW}sh /root/aura-voice.sh${NC}"
echo -e "  ${YELLOW}ruby /opt/aura/scripts/custom_tools.rb${NC}"
echo -e "  ${YELLOW}sh /opt/aura/scripts/panel.sh &${NC}"
echo -e "  ${YELLOW}sh /opt/aura/scripts/wallpaper-rotator.sh &${NC}"
echo -e "  ${YELLOW}sh /opt/aura/scripts/setup-wallpaper-slideshow.sh /ruta/fotos 30 3d${NC}"
echo ""
echo -e "${GREEN}✓ AURA OS Personalizada está lista${NC}"
echo ""
echo -e "${PURPLE}Wallpaper Slideshow:${NC}"
echo -e "  Las fotos se rotan automáticamente cada 30 segundos"
echo -e "  Efecto 3D aplicado automáticamente"
echo -e "  Para agregar fotos: copiarlas a /mnt/usb/wallpapers/"
echo ""

# Iniciar wallpaper rotator si existe
if [ -f /opt/aura/scripts/wallpaper-rotator.sh ]; then
    echo "Iniciando wallpaper rotator..."
    sh /opt/aura/scripts/wallpaper-rotator.sh &
    echo "✓ Wallpaper rotator iniciado"
fi

echo ""

# Mantener sesión activa
echo "Presiona Ctrl+C para salir (los servicios seguirán corriendo)"
echo ""

# Mantener script corriendo
wait
