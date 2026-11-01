#!/usr/bin/env bash
# =============================================================================
# ARIA OS Kali — Setup completo para convertir Kali Linux en entorno dedicado ARIA
# Ejecutar dentro de la VM Kali como root:
#   curl -fsSL https://raw.githubusercontent.com/.../kali-aria-setup.sh | bash
#   o: sudo bash kali-aria-setup.sh
# =============================================================================
set -euo pipefail

ARIA_USER="aria"
ARIA_HOME="/opt/aria"
ARIA_APP_DIR="$ARIA_HOME/ARIA_APP"
VENV_DIR="$ARIA_HOME/venv"
OLLAMA_MODEL="${OLLAMA_MODEL:-granite3.2-vision:2b}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[ARIA]${NC} $*"; }
warn() { echo -e "${YELLOW}[ARIA]${NC} $*"; }
err()  { echo -e "${RED}[ARIA ERROR]${NC} $*" >&2; }

# Verificar root
if [ "$(id -u)" -ne 0 ]; then
    err "Este script debe ejecutarse como root (sudo)"
    exit 1
fi

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ARIA OS Kali — Setup completo de entorno dedicado        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"

# ---------------------------------------------------------------------------
# 1. Actualizar sistema
# ---------------------------------------------------------------------------
log "[1/12] Actualizando repositorios APT..."
apt-get update -qq

# ---------------------------------------------------------------------------
# 2. Instalar dependencias del sistema
# ---------------------------------------------------------------------------
log "[2/12] Instalando dependencias del sistema..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    xfce4 xfce4-terminal lightdm lightdm-gtk-greeter \
    network-manager dbus systemd systemd-resolved \
    util-linux e2fsprogs polkitd policykit-1 \
    ca-certificates gnupg curl wget git rsync \
    unzip tar xz-utils zip vim-nox htop iotop ncdu \
    screen tmux \
    python3 python3-venv python3-pip python3-pyqt5 python3-pyqt5.qtsvg python3-dotenv \
    nmap tcpdump macchanger tor proxychains iw iwlist wireless-tools whois dnsutils \
    iproute2 netcat-openbsd socat jq \
    alsa-utils pulseaudio pipewire pipewire-alsa \
    xserver-xorg xinit xdotool wmctrl x11-xserver-utils mesa-utils \
    ufw nftables zram-tools cryptsetup lvm2 \
    metasploit-framework \
    2>&1 | tail -5

# ---------------------------------------------------------------------------
# 3. Crear usuario aria (sin privilegios sudo innecesarios)
# ---------------------------------------------------------------------------
log "[3/12] Creando usuario $ARIA_USER..."
if ! id "$ARIA_USER" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "$ARIA_USER"
    usermod -aG audio,video,render,plugdev,dialout "$ARIA_USER"
fi
# NO añadir a sudo/adm — usuario de privilegios mínimos

# ---------------------------------------------------------------------------
# 4. Crear estructura /opt/aria
# ---------------------------------------------------------------------------
log "[4/12] Creando estructura /opt/aria..."
mkdir -p "$ARIA_HOME" /var/log/aria /home/"$ARIA_USER"/.config/autostart
chown -R "$ARIA_USER:$ARIA_USER" "$ARIA_HOME" /var/log/aria /home/"$ARIA_USER"

# ---------------------------------------------------------------------------
# 5. Copiar proyecto AURA (desde /opt/aria-build si existe, o descargar)
# ---------------------------------------------------------------------------
log "[5/12] Desplegando proyecto AURA en /opt/aria..."
if [ -d /opt/aria-build/AURA ]; then
    rsync -aHAX --delete /opt/aria-build/AURA/ "$ARIA_APP_DIR/"
elif [ -d /opt/aria/ARIA_APP ]; then
    warn "Ya existe /opt/aria/ARIA_APP, omitiendo copia"
else
    err "No se encontró el proyecto AURA. Colócalo en /opt/aria-build/AURA o ejecuta manualmente."
    exit 1
fi
chown -R "$ARIA_USER:$ARIA_USER" "$ARIA_HOME"

# ---------------------------------------------------------------------------
# 6. Crear .env de ARIA para Kali
# ---------------------------------------------------------------------------
log "[6/12] Configurando .env de ARIA..."
cat > "$ARIA_APP_DIR/.env" <<EOF
ARIA_OLLAMA_URL=http://localhost:11434
ARIA_OLLAMA_MODEL=$OLLAMA_MODEL
ARIA_SYSTEM_PROMPT=Eres ARIA, asistente autónomo nativo sobre Kali Linux. Responde en español. Eres el único proceso de usuario. Sin servidor HTTP, sin puertos abiertos.
AURA_TEMPERATURE=0.7
AURA_MAX_TOKENS=1024
AURA_MEMORY_DIR=$ARIA_HOME/data/memory
AURA_ASSETS_DIR=$ARIA_APP_DIR/assets
EOF
chown "$ARIA_USER:$ARIA_USER" "$ARIA_APP_DIR/.env"

# ---------------------------------------------------------------------------
# 7. Crear venv e instalar dependencias Python
# ---------------------------------------------------------------------------
log "[7/12] Creando entorno Python e instalando dependencias..."
sudo -u "$ARIA_USER" bash -c "
    cd $ARIA_APP_DIR
    python3 -m venv $VENV_DIR
    $VENV_DIR/bin/pip install --upgrade pip
    $VENV_DIR/bin/pip install python-dotenv
    if [ -f requirements.txt ]; then
        $VENV_DIR/bin/pip install -r requirements.txt || true
    fi
"

# ---------------------------------------------------------------------------
# 8. Instalar Ollama y precargar modelo
# ---------------------------------------------------------------------------
log "[8/12] Instalando Ollama y precargando modelo $OLLAMA_MODEL..."
if ! command -v ollama >/dev/null 2>&1; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Iniciar Ollama en segundo plano para precargar modelo
ollama serve &
OLLAMA_PID=$!
sleep 8
ollama pull "$OLLAMA_MODEL" 2>/dev/null || warn "No se pudo precargar $OLLAMA_MODEL (se descargará en primer uso)"
kill "$OLLAMA_PID" 2>/dev/null || true
pkill ollama 2>/dev/null || true

# Habilitar servicio systemd de Ollama si existe
if systemctl list-unit-files 2>/dev/null | grep -q ollama; then
    systemctl enable ollama 2>/dev/null || true
    systemctl start ollama 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# 9. Configurar systemd service de ARIA
# ---------------------------------------------------------------------------
log "[9/12] Configurando systemd service aria-os.service..."
cat > /etc/systemd/system/aria-os.service <<EOF
[Unit]
Description=ARIA OS Native Desktop Agent
Documentation=file:///opt/aria/ARIA_APP/docs/ARIA_OS_NATIVE.md
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=$ARIA_USER
Group=$ARIA_USER
WorkingDirectory=$ARIA_APP_DIR
Environment=PYTHONUNBUFFERED=1
Environment=OLLAMA_HOST=127.0.0.1:11434
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/$ARIA_USER/.Xauthority
ExecStart=$VENV_DIR/bin/python $ARIA_APP_DIR/aria_native.py
Restart=on-failure
RestartSec=5s
StartLimitBurst=10
StartLimitIntervalSec=60
StandardOutput=journal
StandardError=journal
ReadWritePaths=$ARIA_HOME /var/log/aria /home/$ARIA_USER
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=false
PrivateTmp=true

[Install]
WantedBy=graphical-session.target
EOF
systemctl daemon-reload
systemctl enable aria-os.service 2>/dev/null || true

# ---------------------------------------------------------------------------
# 10. Configurar autostart XFCE + LightDM autologin
# ---------------------------------------------------------------------------
log "[10/12] Configurando autostart y autologin..."

# .desktop autostart
cat > /etc/xdg/autostart/aria.desktop <<EOF
[Desktop Entry]
Type=Application
Name=ARIA OS
GenericName=Autonomous AI Agent
Comment=ARIA OS — Agente autónomo nativo, sin servidor, sin puertos
Exec=/usr/local/bin/aria-start.sh
Icon=utilities-terminal
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-XFCE-Autostart-enabled=true
X-KDE-autostart-after=panel
StartupNotify=false
Categories=AI;Agent;System;
EOF

# Launcher aria-start.sh
cat > /usr/local/bin/aria-start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source /opt/aria/venv/bin/activate
cd /opt/aria/ARIA_APP
mkdir -p /var/log/aria
exec python ARIA_APP/aria_native.py >> /var/log/aria/aria.log 2>&1
EOF
chmod +x /usr/local/bin/aria-start.sh

# LightDM autologin usuario aria
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/10-aria-autologin.conf <<EOF
[Seat:*]
autologin-user=$ARIA_USER
autologin-user-timeout=0
user-session=xfce
greeter-session=lightdm-gtk-greeter
EOF

# ---------------------------------------------------------------------------
# 11. Hardening — firewall, servicios off, swappiness, sin navegador
# ---------------------------------------------------------------------------
log "[11/12] Aplicando hardening..."

# Deshabilitar servicios innecesarios
systemctl mask bluetooth.service bluetooth.target 2>/dev/null || true
systemctl mask cups.service cups-browsed.service 2>/dev/null || true
systemctl mask avahi-daemon.service avahi-daemon.socket 2>/dev/null || true
systemctl mask ModemManager.service 2>/dev/null || true
systemctl mask NetworkManager-wait-online.service 2>/dev/null || true
systemctl mask plymouth-start.service plymouth-read-write.service 2>/dev/null || true
systemctl mask whoopsie.service apport.service 2>/dev/null || true
systemctl mask pcscd.service 2>/dev/null || true
systemctl disable ssh.service 2>/dev/null || true
systemctl stop ssh.service 2>/dev/null || true
systemctl disable unattended-upgrades.service 2>/dev/null || true

# Firewall restrictivo (nftables)
cat > /etc/nftables.conf <<'NFTEOF'
#!/usr/sbin/nft -f
flush ruleset
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;
        iifname "lo" accept
        ct state established,related accept
        ct state invalid drop
        icmp type echo-request accept
    }
    chain forward { type filter hook forward priority 0; policy drop; }
    chain output { type filter hook output priority 0; policy accept; }
}
NFTEOF
systemctl enable nftables.service 2>/dev/null || true
systemctl start nftables.service 2>/dev/null || true

# Swappiness baja
cat > /etc/sysctl.d/99-aria-swappiness.conf <<'EOF'
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF
sysctl --system 2>/dev/null || true

# Limitar journald
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/aria.conf <<'EOF'
[Journal]
SystemMaxUse=256M
RuntimeMaxUse=128M
SystemMaxFileSize=50M
RuntimeMaxFileSize=50M
MaxRetentionSec=3day
EOF

# Excluir docs/locales de dpkg (ahorrar espacio)
mkdir -p /etc/dpkg/dpkg.cfg.d
cat > /etc/dpkg/dpkg.cfg.d/99-aria-nodocs <<'EOF'
path-exclude=/usr/share/doc/*
path-include=/usr/share/doc/*/copyright
path-exclude=/usr/share/man/*
path-exclude=/usr/share/groff/*
path-exclude=/usr/share/info/*
path-exclude=/usr/share/lintian/*
path-exclude=/usr/share/locale/*
path-include=/usr/share/locale/en*/
path-include=/usr/share/locale/es*/
EOF

# Quitar navegador por defecto si existe
apt-get remove --purge -y firefox-esr chromium 2>/dev/null || true

# ---------------------------------------------------------------------------
# 12. Limpieza y verificación
# ---------------------------------------------------------------------------
log "[12/12] Limpieza y verificación final..."
apt-get clean -qq
rm -rf /var/lib/apt/lists/*
apt-get autoremove --purge -y -qq 2>/dev/null || true

log "═════════════════════════════════════════════════════════════════"
log "✅ ARIA OS Kali configurado correctamente"
log "═════════════════════════════════════════════════════════════════"
log ""
log "Usuario:       $ARIA_USER (sin privilegios sudo)"
log "Directorio:    $ARIA_APP_DIR"
log "Venv:          $VENV_DIR"
log "Modelo Ollama: $OLLAMA_MODEL"
log ""
log "Verificación:"
log "  sudo systemctl status aria-os"
log "  curl -s http://127.0.0.1:11434/api/tags"
log "  sudo ss -tlnp"
log "  ps aux | grep aria_native"
log ""
log "Reiniciar la VM para que arranque ARIA automáticamente (LightDM autologin)."
