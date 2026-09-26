#!/bin/bash
# AURA OS - Backup Script
# Respaldar toda la configuración y datos de AURA

set -e

BACKUP_DIR="/root/aura-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="aura-backup-${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "╔════════════════════════════════════════════╗"
echo "║     AURA OS - Backup System               ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Crear directorio de backups
mkdir -p "$BACKUP_PATH"

# ============================================
# BACKUP DE CONFIGURACIÓN
# ============================================
echo "[1/5] Backing up configuration..."
mkdir -p "$BACKUP_PATH/config"

# Hyprland config
cp -r /etc/skel/.config/hypr "$BACKUP_PATH/config/" 2>/dev/null || true
cp -r /home/aura/.config/hypr "$BACKUP_PATH/config/" 2>/dev/null || true

# Waybar config
cp -r /etc/skel/.config/waybar "$BACKUP_PATH/config/" 2>/dev/null || true
cp -r /home/aura/.config/waybar "$BACKUP_PATH/config/" 2>/dev/null || true

# GTK/Qt config
cp -r /etc/skel/.config/gtk-3.0 "$BACKUP_PATH/config/" 2>/dev/null || true
cp -r /etc/skel/.config/qt5ct "$BACKUP_PATH/config/" 2>/dev/null || true

# Iconos y themes
cp -r /usr/share/icons/Caelestia "$BACKUP_PATH/config/" 2>/dev/null || true
cp /usr/share/pixmaps/aura-wallpaper.png "$BACKUP_PATH/config/" 2>/dev/null || true

echo "✓ Configuration backed up"

# ============================================
# BACKUP DE SCRIPTS
# ============================================
echo "[2/5] Backing up scripts..."
mkdir -p "$BACKUP_PATH/scripts"

cp -r /opt/aura/scripts "$BACKUP_PATH/" 2>/dev/null || true
cp -r /root/aura-cli.sh "$BACKUP_PATH/scripts/" 2>/dev/null || true
cp -r /root/aura-voice.sh "$BACKUP_PATH/scripts/" 2>/dev/null || true
cp -r /root/aura-personalizada.sh "$BACKUP_PATH/scripts/" 2>/dev/null || true
cp -r /root/aura-start.sh "$BACKUP_PATH/scripts/" 2>/dev/null || true

echo "✓ Scripts backed up"

# ============================================
# BACKUP DE BASE DE DATOS
# ============================================
echo "[3/5] Backing up database..."
mkdir -p "$BACKUP_PATH/database"

# SQLite databases
find /opt/aura -name "*.db" -type f 2>/dev/null | while read db; do
    cp "$db" "$BACKUP_PATH/database/"
done

# PostgreSQL dump
if command -v pg_dump &> /dev/null; then
    pg_dump -U aura aura_db > "$BACKUP_PATH/database/aura_db.sql" 2>/dev/null || true
fi

echo "✓ Database backed up"

# ============================================
# BACKUP DE CONFIGURACIÓN DEL SISTEMA
# ============================================
echo "[4/5] Backing up system configuration..."
mkdir -p "$BACKUP_PATH/system"

# /etc files
cp /etc/hostname "$BACKUP_PATH/system/" 2>/dev/null || true
cp /etc/hosts "$BACKUP_PATH/system/" 2>/dev/null || true
cp /etc/fstab "$BACKUP_PATH/system/" 2>/dev/null || true
cp /etc/resolv.conf "$BACKUP_PATH/system/" 2>/dev/null || true

# Environment
cp /opt/aura/backend/.env "$BACKUP_PATH/system/" 2>/dev/null || true

echo "✓ System configuration backed up"

# ============================================
# COMPRIMIR BACKUP
# ============================================
echo "[5/5] Compressing backup..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

BACKUP_SIZE=$(du -sh "${BACKUP_PATH}.tar.gz" | awk '{print $1}')

echo "✓ Backup compressed"
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     Backup Complete                       ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Backup: ${BACKUP_PATH}.tar.gz"
echo "Size: ${BACKUP_SIZE}"
echo ""
echo "To restore:"
echo "  tar -xzf ${BACKUP_NAME}.tar.gz"
echo "  cd ${BACKUP_NAME}"
echo "  bash restore.sh"
echo ""
