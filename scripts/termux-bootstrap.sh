#!/bin/bash
# AURA OS — Termux Bootstrap Script
# Installs full Linux environment (Ubuntu 22.04 + AURA tools) in Termux
# Run this on Android after installing Termux from F-Droid

set -euo pipefail

echo "═══════════════════════════════════════════════════════════════"
echo "  AURA OS — Termux Bootstrap"
echo "  Installing Linux environment on Android"
echo "═══════════════════════════════════════════════════════════════"

# ─── Check Termux ────────────────────────────────────────────────
if [ ! -d "$PREFIX" ]; then
  echo "❌ ERROR: This script must be run inside Termux."
  echo "   Install Termux from F-Droid: https://f-droid.org/en/packages/com.termux/"
  exit 1
fi

# ─── Update packages ─────────────────────────────────────────────
echo "📦 Updating Termux packages..."
pkg update -y
pkg upgrade -y

# ─── Install core dependencies ───────────────────────────────────
echo "🔧 Installing core packages..."
pkg install -y \
  proot-distro \
  python git wget curl unzip \
  golang nodejs ruby \
  net-tools dnsutils openssh \
  termux-api termux-tools

# ─── Request storage permission (needed for file access) ──────────
echo "📁 Requesting storage permission..."
termux-setup-storage

# ─── Install Ubuntu 22.04 via proot-distro ───────────────────────
echo "🐧 Installing Ubuntu 22.04 (proot-distro)..."
proot-distro install ubuntu-22.04

# ─── Ubuntu setup script ────────────────────────────────────────
UBUNTU_SETUP="
set -e

# Update Ubuntu
apt update -y
apt upgrade -y

# Install system dependencies
apt install -y \\
  python3 python3-pip python3-venv \\
  golang-go \\
  ruby-full \\
  curl wget gnupg \\
  net-tools dnsutils openssh-client \\
  git build-essential \\
  sqlite3 libsqlite3-dev

# Create AURA directory
mkdir -p /opt/aura/backend /opt/aura/logs

# Install Python backend dependencies
pip3 install --break-system-packages \\
  fastapi uvicorn httpx psutil

# Copy AURA Go tools (pre-compiled for arm64)
if [ -d /data/data/com.termux/files/usr/share/aura-tools ]; then
  cp -r /data/data/com.termux/files/usr/share/aura-tools/* /usr/local/bin/
  chmod +x /usr/local/bin/aura-*
fi

# Copy AURA backend
if [ -d /data/data/com.termux/files/home/AURA/backend ]; then
  cp -r /data/data/com.termux/files/home/AURA/backend/* /opt/aura/backend/
fi

# Copy Ruby tools
if [ -d /data/data/com.termux/files/home/AURA/packages/discord-bot ]; then
  cp -r /data/data/com.termux/files/home/AURA/packages/discord-bot /opt/aura/
  cd /opt/aura/discord-bot && bundle install
fi

echo '✅ Ubuntu 22.04 setup complete'
"

echo "$UBUNTU_SETUP" > /data/data/com.termux/files/usr/tmp/aura_ubuntu_setup.sh
proot-distro login ubuntu-22.04 -- sh -c "bash /data/data/com.termux/files/usr/tmp/aura_ubuntu_setup.sh"

# ─── Create AURA helper script ───────────────────────────────────
TERMUX_HELPER="
#!/data/data/com.termux/files/usr/bin/bash
# AURA helper for Termux

case \"\$1\" in
  start)
    proot-distro login ubuntu-22.04 -- python3 /opt/aura/backend/main.py --port 8000 --host 0.0.0.0 &
    echo 'AURA backend started on http://localhost:8000'
    ;;
  stop)
    pkill -f 'python3 /opt/aura/backend/main.py' 2>/dev/null || true
    echo 'AURA backend stopped'
    ;;
  shell)
    proot-distro login ubuntu-22.04
    ;;
  run)
    shift
    proot-distro login ubuntu-22.04 -- \"\$@\"
    ;;
  status)
    curl -s http://localhost:8000/health || echo 'AURA backend not running'
    ;;
  *)
    echo 'Usage: aura <start|stop|shell|run|status>'
    ;;
esac
"

mkdir -p "$HOME/.local/bin"
echo "$TERMUX_HELPER" > "$HOME/.local/bin/aura"
chmod +x "$HOME/.local/bin/aura"

# ─── Copy pre-compiled Go tools ───────────────────────────────────
echo "🔨 Installing Go tools for Android arm64..."
GO_TOOLS_DIST="$HOME/AURA/aura-os/go-tools/dist/android"
if [ -d "$GO_TOOLS_DIST" ]; then
  mkdir -p "$PREFIX/share/aura-tools"
  cp "$GO_TOOLS_DIST"/aura-* "$PREFIX/share/aura-tools/" 2>/dev/null || true
  echo "  Go tools copied to $PREFIX/share/aura-tools/"
else
  echo "  ⚠️  Go tools dist not found at $GO_TOOLS_DIST"
  echo "     Run scripts/cross-compile-go-tools.sh first"
fi

# ─── Install AURA Go tools in Ubuntu ───────────────────────────────
if [ -d "$PREFIX/share/aura-tools" ]; then
  cp "$PREFIX/share/aura-tools"/aura-* "/data/data/com.termux/files/usr/tmp/aura_tools/" 2>/dev/null || {
    mkdir -p /data/data/com.termux/files/usr/tmp/aura_tools/
    cp "$PREFIX/share/aura-tools"/aura-* /data/data/com.termux/files/usr/tmp/aura_tools/
  }
  proot-distro login ubuntu-22.04 -- bash -c "cp /data/data/com.termux/files/usr/tmp/aura_tools/* /usr/local/bin/ && chmod +x /usr/local/bin/aura-*"
fi

# ─── Final verification ──────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ AURA OS Termux setup complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "🚀 Quick start:"
echo "  aura start       # Start AURA backend (localhost:8000)"
echo "  aura shell       # Enter Ubuntu 22.04 environment"
echo "  aura status      # Check backend health"
echo "  aura run aura-scanner -h 192.168.1.1 -p 1 -e 1000"
echo ""
echo "💡 Tips:"
echo "  - Add ~/.local/bin to PATH if not already: export PATH=\$HOME/.local/bin:\$PATH"
echo "  - Storage: termux-setup-storage (grants /sdcard access)"
echo "  - WiFi scan: termux-location (for reconnaissance)"
echo "  - Bluetooth: pkg install termux-api && termux-bluetooth"
echo ""
echo "📱 Install Termux: https://f-droid.org/en/packages/com.termux/"
echo "📄 Full docs: docs/MOBILE-ARCHITECTURE.md"
