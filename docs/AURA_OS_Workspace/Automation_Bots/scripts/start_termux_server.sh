#!/bin/bash
#
# Script para iniciar el servidor y el watcher en Termux
#

# Configuración
PROJECT_DIR="$HOME/AME-termux"
LOG_DIR="$HOME/AME-termux/logs"
SERVER_LOG="$LOG_DIR/servidor.log"
WATCHER_LOG="$LOG_DIR/watcher.log"

# Crear directorio de logs si no existe
mkdir -p "$LOG_DIR"

# Iniciar el servidor en segundo plano y redirigir logs
python3 "$PROJECT_DIR/servidor.py" > "$SERVER_LOG" 2>&1 &

# Esperar un momento para que el servidor inicie
sleep 2

# Iniciar el watcher en segundo plano y redirigir logs
python3 "$PROJECT_DIR/termux_server_watcher.py" > "$WATCHER_LOG" 2>&1 &

echo "Servidor y watcher iniciados en segundo plano."