#!/bin/sh
# AURA OS - Alpine Auto-Installer
# Ejecutar DESPUES de bootear Alpine Linux desde USB
# Uso: sh /mnt/usb/aura-install/aura-installer.sh

set -e

echo "╔════════════════════════════════════════════╗"
echo "║     AURA OS - Alpine Auto-Installer       ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ============================================
# FASE 1: Configurar Alpine
# ============================================
echo "Configurando Alpine..."
apk update
apk add --no-cache \
    bash curl wget git \
    sudo \
    python3 py3-pip \
    postgresql postgresql-contrib \
    redis \
    py3-fastapi py3-uvicorn \
    py3-websockets py3-pydantic py3-aiofiles \
    py3-websockets py3-pydantic py3-aiofiles \
    hyprland wayland libxkbcommon \
    pipewire pipewire-pulse \
    mesa mesa-dri-gallium \
    alacritty ttf-dejavu noto-fonts \
    jq

echo "✓ Alpine configurado"
echo ""

# ============================================
# FASE 2: Crear usuario AURA
# ============================================
echo "Creando usuario aura..."
addgroup -g 1000 aura 2>/dev/null || true
adduser -D -u 1000 -G aura -s /bin/bash aura 2>/dev/null || true
echo "aura:aura123" | chpasswd

echo "✓ Usuario creado"
echo ""

# ============================================
# FASE 3: Setup Python venv
# ============================================
echo "Configurando Python venv..."
mkdir -p /opt/aura/venv
python3 -m venv /opt/aura/venv
. /opt/aura/venv/bin/activate
pip install --upgrade pip setuptools wheel
echo "✓ Python venv configurado"
echo ""

# ============================================
# FASE 4: Copiar AURA backend
# ============================================
echo "Buscando AURA backend..."

AURA_SRC=""

# Buscar en Windows montado read-only
if [ -d /mnt/win/Users/User/Downloads/AURA ]; then
    AURA_SRC=/mnt/win/Users/User/Downloads/AURA
    echo "✓ AURA encontrado en Windows (read-only)"
# Buscar en USB montado
elif [ -d /mnt/usb/AURA ]; then
    AURA_SRC=/mnt/usb/AURA
    echo "✓ AURA encontrado en USB"
elif [ -d /mnt/usb/backend ]; then
    AURA_SRC=/mnt/usb
    echo "✓ Backend encontrado en USB"
elif [ -d /media/sf_AURA ]; then
    AURA_SRC=/media/sf_AURA
    echo "✓ AURA encontrado en carpeta compartida"
elif [ -d /root/AURA ]; then
    AURA_SRC=/root/AURA
    echo "✓ AURA encontrado en /root"
fi

if [ -n "$AURA_SRC" ]; then
    mkdir -p /opt/aura
    cp -r "$AURA_SRC/backend" /opt/aura/ 2>/dev/null || true
    cp -r "$AURA_SRC/scripts" /opt/aura/ 2>/dev/null || true
    cp -r "$AURA_SRC/godot" /opt/aura/ 2>/dev/null || true
    echo "✓ AURA backend copiado"
else
    echo "⚠ AURA no encontrado en USB"
    echo "  Por favor copia manualmente:"
    echo "  cp -r /ruta/a/AURA/backend /opt/aura/"
    echo "  cp -r /ruta/a/AURA/scripts /opt/aura/"
fi

# Copiar dashboard si existe en USB
if [ -f /mnt/usb/aura-install/aura-dashboard.html ]; then
    cp /mnt/usb/aura-install/aura-dashboard.html /opt/aura/ 2>/dev/null || true
    echo "✓ Dashboard copiado"
fi

# Copiar scripts personalizados si existen
if [ -d /mnt/usb/aura-install/scripts ]; then
    cp -r /mnt/usb/aura-install/scripts/* /opt/aura/scripts/ 2>/dev/null || true
    echo "✓ Scripts personalizados copiados"
fi

echo ""

# ============================================
# FASE 5: Instalar dependencias Python
# ============================================
echo "Instalando dependencias Python..."
if [ -f /opt/aura/backend/requirements.txt ]; then
    pip install -r /opt/aura/backend/requirements.txt
    echo "✓ Dependencias instaladas"
else
    echo "⚠ No se encontró requirements.txt"
    echo "  Instalando paquetes básicos..."
    pip install fastapi uvicorn redis websockets pydantic aiofiles python-dotenv
fi
echo ""

# ============================================
# FASE 6: Configurar .env
# ============================================
echo "Configurando ambiente..."
mkdir -p /opt/aura/backend
cat > /opt/aura/backend/.env << 'ENV_FILE'
AURA_HOST=0.0.0.0
AURA_PORT=8000
AURA_ENV=production
DATABASE_URL=sqlite:///./aura.db
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=info
AURA_OS=true
DISPLAY_SERVER=wayland
AURA_MOBILE_SYNC=true
AURA_MOBILE_DISCOVERY_INTERVAL=30
AURA_AUTO_UPDATE=false
AURA_DEBUG_MODE=false
AURA_LIVE_BOOT=true
AURA_PERSIST_ON_USB=true
AURA_LANGUAGE=en_US
AURA_TIMEZONE=America/Argentina/Buenos_Aires
AURA_LOCALE=en_US.UTF-8
AURA_KEYBOARD_LAYOUT=us
ENV_FILE

chown -R aura:aura /opt/aura
echo "✓ Ambiente configurado"
echo ""

# ============================================
# FASE 7: Crear servicios
# ============================================
echo "Configurando servicios..."

# Servicio Redis
cat > /etc/init.d/redis-custom << 'REDIS_SERVICE'
#!/sbin/openrc-run
name="Redis"
description="Redis Server"
command="/usr/bin/redis-server"
command_args="--daemonize yes"
REDIS_SERVICE
chmod +x /etc/init.d/redis-custom

# Script de inicio de AURA
cat > /etc/profile.d/aura-startup.sh << 'STARTUP'
#!/bin/sh
# AURA OS Startup

if [ "$EUID" -eq 0 ]; then
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║      AURA OS - Iniciando servicios         ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    
    echo "Iniciando Redis..."
    redis-server --daemonize yes 2>/dev/null || true
    
    echo "Iniciando AURA Brain..."
    cd /opt/aura
    if [ -d backend ]; then
        cd backend
        . /opt/aura/venv/bin/activate
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
        sleep 2
        echo "✓ AURA Brain iniciado en puerto 8000"
    fi
    
    echo ""
    echo "Backend: http://localhost:8000"
    echo "Health: curl http://localhost:8000/health"
    echo ""
fi
STARTUP

chmod +x /etc/profile.d/aura-startup.sh

echo "✓ Servicios configurados"
echo ""

# ============================================
# FASE 8: Configurar usuario
# ============================================
echo "Configurando usuario aura..."
mkdir -p /home/aura/.config
chown -R aura:aura /home/aura

# Agregar a sudoers
echo "aura ALL=(ALL) ALL" >> /etc/sudoers

echo "✓ Usuario configurado"
echo ""

# ============================================
# FASE 9: Crear scripts CLI y dashboard
# ============================================
echo "Creando scripts de acceso..."

# CLI basico
cat > /root/aura-cli.sh << 'CLISCRIPT'
#!/bin/sh
clear
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          🤖 AURA Personal Assistant v1.0                     ║"
echo "║                                                                ║"
echo "║         Backend: http://localhost:8000                        ║"
echo "║         Type 'exit' to quit                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
API_URL="http://localhost:8000/api/chat"
while true; do
    echo -n "You: "
    read -r user_input
    if [ "$user_input" = "exit" ]; then
        echo ""
        echo "✓ AURA saying goodbye..."
        echo "Goodbye! See you next time."
        break
    fi
    if [ -z "$user_input" ]; then continue; fi
    echo "AURA: Thinking..."
    response=$(curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d "{\"message\": \"$user_input\"}" 2>/dev/null)
    if echo "$response" | grep -q '"response"'; then
        answer=$(echo "$response" | jq -r '.response' 2>/dev/null)
        echo "AURA: $answer"
    else
        echo "AURA: ✗ Error connecting to backend"
    fi
    echo ""
done
CLISCRIPT
chmod +x /root/aura-cli.sh

# CLI con voz
cat > /root/aura-voice.sh << 'VOICESCRIPT'
#!/bin/sh
clear
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     🤖 AURA Personal Assistant v1.0 (WITH VOICE)             ║"
echo "║                                                                ║"
echo "║         Backend: http://localhost:8000                        ║"
echo "║         Voice: espeak (English)                               ║"
echo "║         Type 'exit' to quit                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
API_URL="http://localhost:8000/api/chat"
while true; do
    echo -n "You: "
    read -r user_input
    if [ "$user_input" = "exit" ]; then
        echo ""
        echo "AURA: Goodbye! See you next time."
        espeak "Goodbye! See you next time." 2>/dev/null
        break
    fi
    if [ -z "$user_input" ]; then continue; fi
    echo "AURA: Thinking..."
    response=$(curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d "{\"message\": \"$user_input\"}" 2>/dev/null)
    if echo "$response" | grep -q '"response"'; then
        answer=$(echo "$response" | jq -r '.response' 2>/dev/null)
        echo "AURA: $answer"
        echo "$answer" | espeak -s 150 -p 50 2>/dev/null
    else
        echo "AURA: Error connecting"
        espeak "Error connecting" 2>/dev/null
    fi
    echo ""
done
VOICESCRIPT
chmod +x /root/aura-voice.sh

# Servidor web para dashboard
cat > /root/start-dashboard.sh << 'DASHSCRIPT'
#!/bin/sh
cd /opt/aura
python3 -m http.server 8080
DASHSCRIPT
chmod +x /root/start-dashboard.sh

echo "✓ Scripts CLI y dashboard creados"
echo ""

# ============================================
# FASE 10: Theme 3D y wallpaper
# ============================================
echo "Configurando theme 3D..."

# Buscar foto personalizada en USB
USER_PHOTO=""
if [ -f /mnt/usb/aura-install/wallpaper.jpg ]; then
    USER_PHOTO=/mnt/usb/aura-install/wallpaper.jpg
elif [ -f /mnt/usb/aura-install/wallpaper.png ]; then
    USER_PHOTO=/mnt/usb/aura-install/wallpaper.png
elif [ -f /mnt/usb/wallpaper.jpg ]; then
    USER_PHOTO=/mnt/usb/wallpaper.jpg
elif [ -f /mnt/usb/wallpaper.png ]; then
    USER_PHOTO=/mnt/usb/wallpaper.png
fi

# Ejecutar setup de theme 3D
if [ -f /mnt/usb/aura-install/setup-caelestia-3d.sh ]; then
    cp /mnt/usb/aura-install/setup-caelestia-3d.sh /opt/aura/scripts/
    chmod +x /opt/aura/scripts/setup-caelestia-3d.sh
    sh /opt/aura/scripts/setup-caelestia-3d.sh "$USER_PHOTO"
elif [ -f /opt/aura/scripts/setup-caelestia-3d.sh ]; then
    sh /opt/aura/scripts/setup-caelestia-3d.sh "$USER_PHOTO"
else
    echo "⚠ setup-caelestia-3d.sh no encontrado, usando theme basico"
    # Fallback: configuracion basica sin foto
    mkdir -p /etc/skel/.config/hypr
    cat > /etc/skel/.config/hypr/hyprland.conf << 'HYPRCONF'
monitor=,preferred,auto,1
input { kb_layout = us,es; follow_mouse = 1; }
general { gaps_in = 5; gaps_out = 20; border_size = 2; col.active_border = rgba(8a2be2ff) rgba(38bdf8ff) 45deg; col.inactive_border = rgba(0a0e27ff); layout = master; }
$mainMod = SUPER
bind = $mainMod, Return, exec, alacritty
bind = $mainMod, Q, killactive,
bind = $mainMod, D, exec, wofi --show drun
exec-once = hyprpaper
exec-once = waybar
exec-once = dunst
HYPRCONF
fi

echo "✓ Theme 3D configurado"
echo ""

# ============================================
# FASE 11: Configurar slideshow de wallpapers
# ============================================
echo "Configurando slideshow de wallpapers..."

# Buscar carpeta de wallpapers en USB
WALLPAPER_SRC=""
if [ -d /mnt/usb/wallpapers ]; then
    WALLPAPER_SRC=/mnt/usb/wallpapers
elif [ -d /mnt/usb/aura-install/wallpapers ]; then
    WALLPAPER_SRC=/mnt/usb/aura-install/wallpapers
elif [ -d /mnt/usb/Photos ]; then
    WALLPAPER_SRC=/mnt/usb/Photos
elif [ -d /mnt/usb/Fotos ]; then
    WALLPAPER_SRC=/mnt/usb/Fotos
fi

if [ -n "$WALLPAPER_SRC" ]; then
    echo "  Wallpapers encontrados en: $WALLPAPER_SRC"
    
    # Contar fotos
    PHOTO_COUNT=$(find "$WALLPAPER_SRC" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | wc -l)
    echo "  Fotos detectadas: $PHOTO_COUNT"
    
    if [ "$PHOTO_COUNT" -gt 0 ]; then
        # Copiar setup script
        if [ -f /mnt/usb/aura-install/setup-wallpaper-slideshow.sh ]; then
            cp /mnt/usb/aura-install/setup-wallpaper-slideshow.sh /opt/aura/scripts/
            chmod +x /opt/aura/scripts/setup-wallpaper-slideshow.sh
            
            # Ejecutar setup con intervalo de 30 segundos, efecto 3d
            /opt/aura/scripts/setup-wallpaper-slideshow.sh "$WALLPAPER_SRC" 30 3d
            echo "✓ Slideshow configurado con $PHOTO_COUNT fotos"
        else
            echo "⚠ setup-wallpaper-slideshow.sh no encontrado"
        fi
    else
        echo "⚠ No se encontraron fotos en $WALLPAPER_SRC"
        echo "  Copia tus fotos a la carpeta 'wallpapers' en el USB"
    fi
else
    echo "⚠ No se encontró carpeta de wallpapers"
    echo "  Opciones:"
    echo "    - /mnt/usb/wallpapers"
    echo "    - /mnt/usb/Photos"
    echo "    - /mnt/usb/Fotos"
    echo "  Crea una de estas carpetas y copia tus fotos"
fi

echo "✓ Slideshow de wallpapers procesado"
echo ""

# ============================================
# FIN
# ============================================
echo "╔════════════════════════════════════════════╗"
echo "║   AURA OS - INSTALACIÓN COMPLETADA        ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Usuario: aura"
echo "Password: aura123"
echo ""
echo "Backend: http://localhost:8000"
echo "WebSocket: ws://localhost:8000/ws/telemetry"
echo ""
echo "Comandos utiles:"
echo "  sh /root/aura-cli.sh         # Chat de texto"
echo "  sh /root/aura-voice.sh       # Chat con voz"
echo "  sh /root/start-dashboard.sh  # Dashboard web en :8080"
echo "  curl http://localhost:8000/health"
echo ""
echo "Próximos pasos:"
echo "1. Reboot: reboot"
echo "2. Login como 'aura'"
echo "3. Backend se inicia automáticamente"
echo "4. Probar CLI: sh /root/aura-cli.sh"
echo ""
echo "✓ AURA OS está listo"
