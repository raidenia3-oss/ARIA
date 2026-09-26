#!/bin/bash
# Script para terminar sesion PC-Termux y ahorrar bateria
# Ejecutar en Termux: bash ~/terminar_sesion.sh

echo "=== TERMINANDO SESION PC-TERMUX ==="
echo ""

# 1. Detener sshd
echo "1. Deteniendo sshd..."
pkill sshd 2>/dev/null
sleep 1

if pgrep sshd > /dev/null; then
    echo "   sshd DETENIDO"
else
    echo "   sshd ya estaba detenido"
fi

# 2. Liberar wake-lock
echo "2. Liberando bloqueo de pantalla..."
termux-wake-unlock
echo "   Pantalla liberada"

# 3. Matar keep-alive si existe
echo "3. Limpiando procesos..."
pkill -f "sshd 2>/dev/null" 2>/dev/null
echo "   Procesos de fondo limpiados"

echo ""
echo "=========================================="
echo "  SESION TERMINADA"
echo "  AHORRANDO BATERIA"
echo "=========================================="
echo ""
echo "Para reconectar mas tarde:"
echo "  bash ~/iniciar_sesion.sh"
echo ""