#!/data/data/com.termux/files/usr/bin/bash
# Script de inicio rapido SSH para Termux
# Ejecutar en Termux: bash start_ssh_termux.sh

set -e

echo "=== AURA Termux SSH Setup ==="

# Instalar openssh si falta
if ! command -v sshd >/dev/null 2>&1; then
    echo "[1/4] Instalando openssh..."
    pkg install -y openssh
else
    echo "[1/4] openssh ya instalado"
fi

# Generar claves host si falta
if [ ! -f /data/data/com.termux/files/usr/etc/ssh/ssh_host_rsa_key ]; then
    echo "[2/4] Generando claves host..."
    ssh-keygen -A
else
    echo "[2/4] Claves host listas"
fi

# Preparar directorio .ssh
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Leer clave publica de la PC si esta en el portapapeles o archivo
PUBKEY_FILE="$HOME/aura_pubkey.pub"
if [ -f "$PUBKEY_FILE" ]; then
    echo "[3/4] Instalando clave publica desde $PUBKEY_FILE..."
    grep -q -F -f "$PUBKEY_FILE" ~/.ssh/authorized_keys 2>/dev/null || cat "$PUBKEY_FILE" >> ~/.ssh/authorized_keys
else
    echo "[3/4] Sin clave publica local. Copiala manualmente a ~/.ssh/authorized_keys"
fi

chmod 600 ~/.ssh/authorized_keys 2>/dev/null || true

# Iniciar sshd
echo "[4/4] Iniciando sshd en puerto 8022..."
pkill sshd 2>/dev/null || true
sshd -p 8022

sleep 1

echo ""
echo "=== Estado ==="
if pgrep -x sshd >/dev/null; then
    echo "OK: sshd corriendo"
else
    echo "ERROR: sshd no esta corriendo"
fi

echo "IP local: $(hostname -I | awk '{print $1}')"
echo "Usuario: $(whoami)"
echo ""
echo "Para detener sshd: pkill sshd"
echo "Para ver logs: logcat -s sshd"
