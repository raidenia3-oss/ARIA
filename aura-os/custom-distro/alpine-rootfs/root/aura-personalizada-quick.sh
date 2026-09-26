#!/bin/bash
# AURA OS Personalizada - Quick Start
# Inicio rápido para Alpine Live USB

set -e

echo "╔════════════════════════════════════════════╗"
echo "║   AURA OS Personalizada - Quick Start     ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Detectar USB
USB_MOUNT=""
if [ -d /mnt/usb/aura-install ]; then
    USB_MOUNT=/mnt/usb
elif [ -d /mnt/usb1/aura-install ]; then
    USB_MOUNT=/mnt/usb1
elif [ -d /mnt/usb0/aura-install ]; then
    USB_MOUNT=/mnt/usb0
fi

if [ -n "$USB_MOUNT" ]; then
    echo "[+] USB detectado en $USB_MOUNT"
    
    # Copiar scripts personalizados
    if [ -f "$USB_MOUNT/aura-install/aura-personalizada.sh" ]; then
        cp "$USB_MOUNT/aura-install/aura-personalizada.sh" /root/
        chmod +x /root/aura-personalizada.sh
        echo "[+] Script personalizado copiado"
    fi
fi

# Verificar si ya está instalado
if [ -f /root/aura-personalizada.sh ]; then
    echo "[+] Iniciando AURA OS Personalizada..."
    exec /root/aura-personalizada.sh
else
    echo "[!] Primero ejecuta: sh /mnt/usb/aura-install/aura-installer.sh"
    echo "    Luego ejecuta: sh /root/aura-personalizada.sh"
fi
