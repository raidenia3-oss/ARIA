#!/usr/bin/env bash
# AURA OS - Quick Install Script
# Instala AURA OS en Arch Linux base

set -euo pipefail

echo "╔════════════════════════════════════════════╗"
echo "║     AURA OS - Quick Install Script        ║"
echo "╚════════════════════════════════════════════╝"

# 1. Verificar root
if [[ $EUID -ne 0 ]]; then
    echo "[!] Ejecutar como root: sudo bash quick_install_aura_os.sh"
    exit 1
fi

# 2. Actualizar sistema
echo "[+] Actualizando sistema..."
pacman -Syu --noconfirm

# 3. Instalar dependencias
echo "[+] Instalando dependencias..."
pacman -S --noconfirm hyprland wayland waybar rofi-wayland kitty pipewire pipewire-pulse python python-pip git ufw brightnessctl postgresql redis

# 4. Crear usuario aura
echo "[+] Creando usuario aura..."
if ! id aura &>/dev/null; then
    useradd --create-home --shell /bin/bash aura
    usermod -aG wheel aura
fi

# 5. Configurar directorios
echo "[+] Configurando directorios..."
mkdir -p /opt/aura
mkdir -p /etc/aura
chown -R aura:aura /home/aura

# 6. Copiar AURA backend
echo "[+] Copiando AURA backend..."
cp -r /root/AURA/backend /opt/aura/
cp -r /root/AURA/scripts /opt/aura/
cp -r /root/AURA/godot /opt/aura/

# 7. Setup Python venv
echo "[+] Configurando entorno Python..."
cd /opt/aura/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 8. Instalar systemd services
echo "[+] Instalando systemd services..."
cp /root/AURA/aura-os/systemd/*.service /etc/systemd/system/
cp /root/AURA/aura-os/systemd/*.target /etc/systemd/system/
systemctl daemon-reload
systemctl enable aura-brain.service
systemctl enable aura-shell.service

# 9. Configurar Hyprland
echo "[+] Configurando Hyprland..."
mkdir -p /home/aura/.config/hypr
cat > /home/aura/.config/hypr/hyprland.conf << 'EOF'
# AURA OS Hyprland Config
monitor=,preferred,auto,1

exec-once = /opt/aura/aura_shell_linux.x86_64 --no-window --fullscreen
exec-once = waybar

windowrule = float, ^(aura_shell)$
windowrule = noborder, ^(aura_shell)$
windowrule = fullscreen, ^(aura_shell)$
windowrule = opacity 0.9 0.9, ^(aura_shell)$

bind = SUPER, Q, exec, kitty
bind = SUPER, C, killactive,
bind = SUPER, M, exit,
EOF
chown -R aura:aura /home/aura/.config

# 10. Configurar variables de entorno
echo "[+] Configurando variables de entorno..."
cp /root/AURA/backend/.env /etc/aura/aura.env

# 11. Habilitar servicios
echo "[+] Habilitando servicios..."
systemctl enable aura-brain.service
systemctl enable aura-shell.service

# 12. Iniciar servicios
echo "[+] Iniciando servicios..."
systemctl start aura-brain.service
systemctl start aura-shell.service

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║    AURA OS Instalado Correctamente        ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Próximos pasos:"
echo "  1. Reiniciar el sistema"
echo "  2. Seleccionar Hyprland en el login"
echo "  3. AURA OS iniciará automáticamente"
echo ""
echo "Para probar el backend:"
echo "  curl http://localhost:8000/health"
echo ""
