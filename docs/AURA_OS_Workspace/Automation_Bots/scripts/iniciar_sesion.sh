#!/bin/bash
# Script para iniciar sesion PC-Termux
# Ejecutar en Termux: bash ~/iniciar_sesion.sh

echo "=== INICIANDO SESION PC-TERMUX ==="
echo ""

# 1. Mantener pantalla encendida
echo "1. Bloqueando pantalla..."
termux-wake-lock

# 2. Iniciar sshd
echo "2. Iniciando sshd..."
sshd

# 3. Mostrar IP actual
echo "3. IP actual:"
ip addr show wlan0 2>/dev/null | grep "inet " | head -1
echo ""

# 4. Verificar que sshd esta corriendo
echo "4. Estado de sshd:"
if pgrep sshd > /dev/null; then
    echo "   sshd ACTIVO (PID: $(pgrep sshd))"
    PORT=$(netstat -tlnp 2>/dev/null | grep ":8022 " | awk '{print $4}' | cut -d: -f2)
    if [ -n "$PORT" ]; then
        echo "   Puerto: $PORT"
    else
        echo "   Puerto: 8022 (configurado)"
    fi
else
    echo "   sshd INACTIVO"
fi

# 5. Mantener sshd vivo en segundo plano
echo "5. Iniciando keep-alive..."
nohup bash -c "while true; do sshd 2>/dev/null; sleep 30; done" > /dev/null 2>&1 &

echo ""
echo "=========================================="
echo "  LISTO PARA CONECTAR DESDE PC"
echo "=========================================="
echo ""
echo "Comando para conectar desde PC:"
echo "  ssh -p 8022 u0_a1167@$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -1)"
echo ""
echo "Para terminar la sesion, ejecuta: bash ~/terminar_sesion.sh"