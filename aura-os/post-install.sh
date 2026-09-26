#!/bin/bash

# AURA OS — Post-Installation Setup

set -e

echo "╔════════════════════════════════════╗"
echo "║   AURA OS Post-Install Setup       ║"
echo "╚════════════════════════════════════╝"

# Check if root
if [ "$EUID" -ne 0 ]; then
    echo "[-] This script must be run as root"
    exit 1
fi

# Create AURA user if not exists
if ! id -u aura > /dev/null 2>&1; then
    echo "[*] Creating aura user..."
    addgroup -g 1000 aura
    adduser -D -u 1000 -G aura -s /bin/bash aura
    echo "aura ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
    echo "[+] User aura created"
fi

# Setup directories
echo "[*] Creating directories..."
mkdir -p /opt/aura/{go-tools,ruby-tools,backend}
mkdir -p /home/aura/.config/{hyprland,waybar}
chown -R aura:aura /opt/aura /home/aura

# Build Go tools if source available
if [ -d "/opt/aura/go-tools/src" ]; then
    echo "[*] Building Go tools..."
    cd /opt/aura/go-tools
    go mod tidy
    make build 2>/dev/null || echo "[!] Go build skipped"
    chmod +x bin/* 2>/dev/null || true
    ln -sf bin/* /usr/local/bin/ 2>/dev/null || true
fi

# Setup Ruby tools
if [ -d "/opt/aura/ruby-tools" ]; then
    echo "[*] Setting up Ruby tools..."
    cd /opt/aura/ruby-tools
    bundle install --system 2>/dev/null || echo "[!] Bundle install skipped"
    chmod +x bin/*
    ln -sf bin/* /usr/local/bin/ 2>/dev/null || true
fi

# Setup Python backend
if [ -d "/opt/aura/backend" ]; then
    echo "[*] Setting up AURA backend..."
    cd /opt/aura/backend
    pip install -r requirements.txt 2>/dev/null || echo "[!] Pip install skipped"
    python -m py_compile main.py 2>/dev/null || echo "[!] Backend compilation skipped"
fi

# Configure timezone
echo "[*] Setting timezone..."
ln -sf /usr/share/zoneinfo/UTC /etc/localtime

# Setup SSH
echo "[*] Configuring SSH..."
ssh-keygen -A 2>/dev/null || true
rc-service sshd start 2>/dev/null || true

# Setup network
echo "[*] Configuring network..."
cat > /etc/network/interfaces << 'EOF'
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF

# Configure Hyprland
if [ -f /home/aura/.config/hyprland/hyprland.conf ]; then
    echo "[+] Hyprland configured"
fi

# Create systemd service for AURA backend
echo "[*] Creating systemd service..."
cat > /etc/systemd/system/aura.service << 'EOF'
[Unit]
Description=AURA OS Backend Service
After=network.target

[Service]
Type=simple
User=aura
WorkingDirectory=/opt/aura/backend
ExecStart=/usr/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload 2>/dev/null || true
systemctl enable aura 2>/dev/null || true

echo ""
echo "╔════════════════════════════════════╗"
echo "║   Setup Complete!                  ║"
echo "╚════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Reboot: reboot"
echo "  2. Login as aura user"
echo "  3. Start AURA: systemctl start aura"
echo "  4. Access API: http://localhost:8000/api/docs"
echo ""
