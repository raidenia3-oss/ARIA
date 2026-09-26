#!/bin/bash
# AURA OS - Post-Install Script
# Ejecutar DESPUÉS del primer boot en AURA OS
# Uso: bash post-install.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     AURA OS - Post Install Script        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"

# ============================================
# FASE 0: Verificaciones previas
# ============================================
echo -e "\n${YELLOW}[FASE 0] Verificando sistema...${NC}"

if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}ERROR: No ejecutar como root. Ejecutar como usuario 'aura'.${NC}"
    exit 1
fi

if ! ping -c 1 8.8.8.8 &> /dev/null; then
    echo -e "${RED}ERROR: Sin conexión a internet${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Conexión a internet OK${NC}"

# ============================================
# FASE 1: Instalar stack visual completo
# ============================================
echo -e "\n${YELLOW}[FASE 1] Instalando stack visual...${NC}"

sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm \
    hyprland hyprlock hyprpaper hyprcursor hyprwayland-protocols \
    wayland wayland-protocols \
    waybar wofi dunst \
    alacritty kitty \
    qt5-wayland qt6-wayland \
    xorg-xwayland \
    pipewire pipewire-pulse pavucontrol \
    noto-fonts noto-fonts-emoji \
    qt5ct qt6ct \
    polkit gnome-keyring \
    curl wget git

echo -e "${GREEN}✓ Stack visual instalado${NC}"

# ============================================
# FASE 2: Detectar e instalar drivers GPU
# ============================================
echo -e "\n${YELLOW}[FASE 2] Detectando GPU e instalando drivers...${NC}"

GPU_DETECTED=$(lspci | grep -E "NVIDIA|AMD" | head -1)

if echo "$GPU_DETECTED" | grep -qi "NVIDIA"; then
    echo -e "${BLUE}Detectado GPU NVIDIA. Instalando drivers...${NC}"
    sudo pacman -S --noconfirm nvidia-dkms nvidia-utils opencl-nvidia egl-wayland
    echo -e "${GREEN}✓ Drivers NVIDIA instalados${NC}"
elif echo "$GPU_DETECTED" | grep -qi "AMD"; then
    echo -e "${BLUE}Detectado GPU AMD. Instalando drivers...${NC}"
    sudo pacman -S --noconfirm mesa vulkan-radeon xf86-video-amdgpu
    echo -e "${GREEN}✓ Drivers AMD instalados${NC}"
else
    echo -e "${YELLOW}⚠ GPU no detectada. Instalando drivers genéricos...${NC}"
    sudo pacman -S --noconfirm mesa vulkan-icd-loader
    echo -e "${GREEN}✓ Drivers genéricos instalados${NC}"
fi

# ============================================
# FASE 3: Instalar Godot 4.x
# ============================================
echo -e "\n${YELLOW}[FASE 3] Instalando Godot 4.x...${NC}"

if ! command -v godot &> /dev/null; then
    echo -e "${BLUE}Descargando Godot 4...${NC}"
    cd /tmp
    GODOT_VERSION="4.6-stable"
    GODOT_FILE="Godot_v${GODOT_VERSION}_linux.x86_64.zip"
    wget -q "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}/${GODOT_FILE}"
    unzip -q "$GODOT_FILE"
    sudo mv Godot_v${GODOT_VERSION}_linux.x86_64 /usr/local/bin/godot
    sudo chmod +x /usr/local/bin/godot
    rm -f "$GODOT_FILE"
    echo -e "${GREEN}✓ Godot instalado en /usr/local/bin/godot${NC}"
else
    echo -e "${GREEN}✓ Godot ya instalado${NC}"
fi

# ============================================
# FASE 4: Montar Windows y copiar backend AURA
# ============================================
echo -e "\n${YELLOW}[FASE 4] Montando Windows y copiando backend...${NC}"

WINDOWS_MOUNT="/mnt/windows"
WINDOWS_PART=""
AURA_SOURCE=""

# Detectar partición Windows automáticamente
for part in /dev/nvme0n1p* /dev/sda* /dev/sdb*; do
    if [ -b "$part" ]; then
        fs_type=$(sudo blkid -o value -s TYPE "$part" 2>/dev/null || echo "")
        if [[ "$fs_type" == "ntfs" ]] || [[ "$fs_type" == "fuseblk" ]]; then
            WINDOWS_PART="$part"
            break
        fi
    fi
done

if [ -z "$WINDOWS_PART" ]; then
    echo -e "${YELLOW}No se detectó partición Windows automáticamente${NC}"
    echo -e "${BLUE}Particiones disponibles:${NC}"
    sudo fdisk -l | grep -E "Device|NTFS|EFI"
    echo ""
    read -p "Ingresa la partición Windows (ej: /dev/nvme0n1p3): " WINDOWS_PART
fi

if [ -z "$WINDOWS_PART" ]; then
    echo -e "${RED}ERROR: No se especificó partición Windows${NC}"
    exit 1
fi

echo -e "${BLUE}Montando $WINDOWS_PART en modo lectura...${NC}"
sudo mkdir -p "$WINDOWS_MOUNT"
sudo mount -t ntfs-3g -o ro "$WINDOWS_PART" "$WINDOWS_MOUNT"

if [ ! -d "$WINDOWS_MOUNT/Users" ]; then
    echo -e "${RED}ERROR: Partición montada no parece ser Windows${NC}"
    sudo umount "$WINDOWS_MOUNT"
    exit 1
fi

echo -e "${GREEN}✓ Windows montado en $WINDOWS_MOUNT (solo lectura)${NC}"

# Buscar AURA backend en Windows
echo -e "${BLUE}Buscando AURA backend en Windows...${NC}"
AURA_SOURCE=""
for user_dir in "$WINDOWS_MOUNT"/Users/*; do
    if [ -d "$user_dir/Downloads/AURA/backend" ]; then
        AURA_SOURCE="$user_dir/Downloads/AURA"
        break
    fi
done

if [ -z "$AURA_SOURCE" ]; then
    echo -e "${YELLOW}No se encontró AURA en la ruta esperada${NC}"
    echo -e "${BLUE}Buscando en todo el sistema de archivos...${NC}"
    AURA_SOURCE=$(sudo find "$WINDOWS_MOUNT" -maxdepth 5 -type d -name "AURA" 2>/dev/null | head -1)
fi

if [ -z "$AURA_SOURCE" ]; then
    echo -e "${RED}ERROR: No se encontró la carpeta AURA en Windows${NC}"
    echo -e "${YELLOW}Por favor, copia manualmente:${NC}"
    echo -e "  cp -r /mnt/windows/Users/TU_USUARIO/Downloads/AURA/backend /opt/aura/"
    echo -e "  cp -r /mnt/windows/Users/TU_USUARIO/Downloads/AURA/scripts /opt/aura/"
    echo -e "  cp -r /mnt/windows/Users/TU_USUARIO/Downloads/AURA/godot /opt/aura/shell/"
    sudo umount "$WINDOWS_MOUNT"
    exit 1
fi

echo -e "${GREEN}✓ AURA encontrado en: $AURA_SOURCE${NC}"

sudo mkdir -p /opt/aura
sudo cp -r "$AURA_SOURCE/backend" /opt/aura/
sudo cp -r "$AURA_SOURCE/scripts" /opt/aura/
sudo cp -r "$AURA_SOURCE/godot" /opt/aura/shell/ 2>/dev/null || true
sudo chown -R aura:aura /opt/aura

echo -e "${GREEN}✓ Backend copiado a /opt/aura/${NC}"

# Desmontar Windows
sudo umount "$WINDOWS_MOUNT"
echo -e "${GREEN}✓ Windows desmontado${NC}"

# ============================================
# FASE 5: Configurar Python venv
# ============================================
echo -e "\n${YELLOW}[FASE 5] Configurando entorno Python...${NC}"

if [ ! -d "/opt/aura/backend" ]; then
    echo -e "${RED}ERROR: /opt/aura/backend no existe${NC}"
    echo -e "${YELLOW}Asegurate de haber copiado el backend desde Windows${NC}"
    exit 1
fi

cd /opt/aura
sudo -u aura python3 -m venv venv
sudo -u aura bash -c 'source venv/bin/activate && pip install --upgrade pip setuptools wheel'
sudo -u aura bash -c 'source venv/bin/activate && pip install -r backend/requirements.txt'

echo -e "${GREEN}✓ Python venv configurado${NC}"

# ============================================
# FASE 6: Configurar servicios systemd
# ============================================
echo -e "\n${YELLOW}[FASE 6] Configurando servicios systemd...${NC}"

sudo mkdir -p /etc/systemd/system

cat > /etc/systemd/system/aura-brain.service << 'SERVICE'
[Unit]
Description=AURA Brain (FastAPI Backend)
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=aura
WorkingDirectory=/opt/aura/backend
ExecStart=/opt/aura/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
Environment="PATH=/opt/aura/venv/bin"

[Install]
WantedBy=multi-user.target
SERVICE

cat > /etc/systemd/system/aura-gesture.service << 'SERVICE'
[Unit]
Description=AURA Gesture Control
After=display-manager.service

[Service]
Type=simple
User=aura
ExecStart=python3 /opt/aura/gesture/gesture_control.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable aura-brain aura-gesture
sudo systemctl start aura-brain aura-gesture

echo -e "${GREEN}✓ Servicios systemd habilitados e iniciados${NC}"

# ============================================
# FASE 7: Configurar Hyprland
# ============================================
echo -e "\n${YELLOW}[FASE 7] Configurando Hyprland...${NC}"

sudo mkdir -p /home/aura/.config/hypr
sudo chown -R aura:aura /home/aura/.config

cat > /home/aura/.config/hypr/hyprland.conf << 'HYPR_CONF'
monitor=,preferred,auto,1

input {
    kb_layout = us,es
    follow_mouse = 1
    float_switch_override_focus = 2
}

general {
    gaps_in = 5
    gaps_out = 20
    border_size = 2
    col.active_border = rgba(8a2be2ff) rgba(38bdf8ff) 45deg
    col.inactive_border = rgba(0a0e27ff)
    layout = master
}

decoration {
    rounding = 10
    drop_shadow = yes
    shadow_range = 4
    shadow_render_power = 3
    col.shadow = rgba(1a1a2eff)
}

animations {
    enabled = yes
    bezier = myBezier, 0.05, 0.9, 0.1, 1.05
    animation = windows, 1, 7, myBezier
    animation = windowsOut, 1, 7, default, popin 80%
    animation = border, 1, 10, default
    animation = fade, 1, 7, default
}

dwindle {
    pseudotile = yes
    preserve_split = yes
}

master {
    new_status = master
}

misc {
    force_default_wallpaper = 0
}

$mainMod = SUPER

bind = $mainMod, Return, exec, alacritty
bind = $mainMod, D, exec, wofi --show drun
bind = $mainMod, Q, killactive,
bind = $mainMod, M, exit,
bind = $mainMod, V, togglefloating,
bind = $mainMod, P, pseudo,
bind = $mainMod, A, exec, /opt/aura/shell/aura-shell

bind = $mainMod, 1, workspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod, 3, workspace, 3

bind = $mainMod, left, movefocus, l
bind = $mainMod, right, movefocus, r
bind = $mainMod, up, movefocus, u
bind = $mainMod, down, movefocus, d

bind = $mainMod SHIFT, left, resizeactive, -50 0
bind = $mainMod SHIFT, right, resizeactive, 50 0

bind = , XF86AudioRaiseVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ +5%
bind = , XF86AudioLowerVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ -5%
bind = , XF86AudioMute, exec, pactl set-sink-mute @DEFAULT_SINK@ toggle

exec-once = hyprpaper
exec-once = dunst
exec-once = waybar
exec-once = systemctl --user start aura-brain.service
exec-once = systemctl --user start aura-gesture.service
HYPR_CONF

echo -e "${GREEN}✓ Hyprland configurado${NC}"

# ============================================
# FASE 8: Verificación final
# ============================================
echo -e "\n${YELLOW}[FASE 8] Verificación final...${NC}"

echo -e "${BLUE}Verificando servicios...${NC}"
if systemctl --user is-active --quiet aura-brain.service; then
    echo -e "${GREEN}✓ AURA Brain corriendo${NC}"
else
    echo -e "${RED}✗ AURA Brain no está corriendo${NC}"
fi

if systemctl --user is-active --quiet aura-gesture.service; then
    echo -e "${GREEN}✓ AURA Gesture corriendo${NC}"
else
    echo -e "${RED}✗ AURA Gesture no está corriendo${NC}"
fi

echo -e "${BLUE}Verificando backend...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Backend responde en puerto 8000${NC}"
else
    echo -e "${YELLOW}⚠ Backend no responde todavía (puede tardar unos segundos)${NC}"
fi

echo -e "\n${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     POST-INSTALL COMPLETADO              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"

echo -e "\nPróximos pasos:"
echo "1. Reiniciar: sudo reboot"
echo "2. En GRUB, seleccionar 'AURA_OS'"
echo "3. Login: usuario 'aura', contraseña 'aura123'"
echo "4. Hyprland debería iniciar automáticamente"
echo ""
echo "Comandos útiles:"
echo "  systemctl --user status aura-brain"
echo "  systemctl --user status aura-gesture"
echo "  curl http://localhost:8000/health"
echo ""
echo -e "${YELLOW}IMPORTANTE:${NC}"
echo "  - Windows NO fue modificado"
echo "  - Para volver a Windows: reiniciar y seleccionar 'Windows Boot Manager' en GRUB"
echo ""
