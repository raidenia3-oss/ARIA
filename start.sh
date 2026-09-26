#!/usr/bin/env bash
# AURA Launcher for Unix/Mac
# ./start.sh to start AURA in development mode

set -e

echo ""
echo "========================================"
echo "  AURA Development Launcher"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "[WARN] Node.js not found. Frontend will be skipped."
fi

# Check Ruby
if ! command -v ruby &> /dev/null; then
    echo "[WARN] Ruby not found. Discord bot will be skipped."
fi

echo "[INFO] Starting AURA in development mode..."
echo ""

python3 aura.py
