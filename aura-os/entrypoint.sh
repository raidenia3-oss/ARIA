#!/bin/bash

# AURA OS Entrypoint

set -e

echo "╔════════════════════════════════════╗"
echo "║   AURA OS v2.1 — Booting...       ║"
echo "╚════════════════════════════════════╝"

# Check if running in container/VM
if [ -f /.dockerenv ]; then
    echo "[*] Running in Docker"
fi

# Setup environment
export AURA_HOME=/opt/aura
export PATH="${AURA_HOME}/go-tools:${AURA_HOME}/ruby-tools/bin:${PATH}"

# Create necessary directories
mkdir -p ~/.config/hyprland
mkdir -p ~/.local/share/applications

# Start AURA backend if not already running
if ! pgrep -f "python.*main.py" > /dev/null; then
    echo "[*] Starting AURA backend..."
    cd "${AURA_HOME}/backend"
    python main.py &
    AURA_PID=$!
    echo "[+] AURA backend started (PID: $AURA_PID)"
    
    # Wait for backend to be ready
    sleep 3
    
    # Verify connectivity
    if curl -s http://localhost:8000/api/health > /dev/null; then
        echo "[+] AURA backend is healthy"
    else
        echo "[-] AURA backend failed to start"
    fi
fi

# Start mDNS discovery
echo "[*] Starting mDNS discovery (aura.local)..."
if command -v avahi-daemon &> /dev/null; then
    sudo avahi-daemon --daemonize || true
fi

# Print available tools
echo ""
echo "╔════════════════════════════════════╗"
echo "║     Available Tools                ║"
echo "╚════════════════════════════════════╝"
echo ""
echo "  [Network Tools]"
echo "    • aura-scanner       — Port scanner"
echo "    • aura-resolver      — DNS resolver"
echo "    • aura-enum          — Subdomain enumerator"
echo ""
echo "  [C2 Framework]"
echo "    • aura-c2-server     — C2 controller"
echo "    • aura-c2-agent      — Deploy agent"
echo "    • aura-c2-client     — CLI client"
echo ""
echo "  [Penetration Testing]"
echo "    • aura-pentest       — Security testing suite"
echo "    • aura-ruby          — Ruby CLI tools"
echo ""
echo "  [AURA API]"
echo "    • http://localhost:8000/api/docs"
echo "    • ws://localhost:8000/ws (WebSocket)"
echo ""
echo "  [Shortcuts]"
echo "    • Super+A     → AURA Chat"
echo "    • Super+C     → C2 Console"
echo "    • Super+P     → Pentest Help"
echo "    • Super+M     → Port Scanner"
echo ""

# Execute command or start shell
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec /bin/bash --login
fi
