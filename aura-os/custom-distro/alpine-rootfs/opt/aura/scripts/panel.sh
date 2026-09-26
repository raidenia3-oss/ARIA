#!/bin/bash
# AURA Custom Panel - Caelestia Style
# Panel superior con información del sistema

PANEL_WIDTH=100%
PANEL_HEIGHT=32
PANEL_BG="rgba(10, 14, 39, 0.95)"
PANEL_FG="#38bdf8"
PANEL_ACCENT="#8a2be2"

# Actualizar cada segundo
while true; do
    # Obtener información del sistema
    DATE=$(date '+%H:%M:%S')
    DATE_FULL=$(date '+%Y-%m-%d')
    UPTIME=$(uptime -p 2>/dev/null || echo "N/A")
    CPU=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 || echo "N/A")
    MEM=$(free -h 2>/dev/null | grep "Mem:" | awk '{print $3 "/" $2}' || echo "N/A")
    
    # Construir panel con waybar o simple echo
    # Para Alpine live usamos un simple echo con formato
    printf "\r\033[1;35m%s\033[0m | \033[1;36mCPU: %s%%\033[0m | \033[1;36mMEM: %s\033[0m | \033[1;35m%s\033[0m" \
        "$DATE" "$CPU" "$MEM" "$UPTIME"
    
    sleep 1
done
