#!/bin/bash
# AURA OS - Restore Script
# Restaurar configuración y datos desde backup

set -e

echo "╔════════════════════════════════════════════╗"
echo "║     AURA OS - Restore System              ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Buscar backups
BACKUP_DIR="/root/aura-backups"
if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: No backup directory found at $BACKUP_DIR"
    exit 1
fi

# Listar backups disponibles
echo "Available backups:"
ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""

# Pedir backup a restaurar
echo -n "Enter backup name (or path): "
read -r BACKUP_NAME

if [ -z "$BACKUP_NAME" ]; then
    echo "ERROR: Backup name required"
    exit 1
fi

# Si no tiene extensión, agregarla
if [[ "$BACKUP_NAME" != *.tar.gz ]]; then
    BACKUP_NAME="${BACKUP_NAME}.tar.gz"
fi

# Verificar que existe
if [ ! -f "$BACKUP_NAME" ]; then
    # Buscar en directorio de backups
    if [ -f "$BACKUP_DIR/$BACKUP_NAME" ]; then
        BACKUP_NAME="$BACKUP_DIR/$BACKUP_NAME"
    else
        echo "ERROR: Backup not found: $BACKUP_NAME"
        exit 1
    fi
fi

echo ""
echo "Restoring from: $BACKUP_NAME"
echo ""

# Extraer backup
TEMP_DIR="/tmp/aura-restore-$$"
mkdir -p "$TEMP_DIR"
tar -xzf "$BACKUP_NAME" -C "$TEMP_DIR"

# Encontrar directorio extraído
EXTRACTED_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d | head -1)

# ============================================
# RESTAURAR CONFIGURACIÓN
# ============================================
echo "[1/4] Restoring configuration..."
if [ -d "$EXTRACTED_DIR/config" ]; then
    cp -r "$EXTRACTED_DIR/config/hypr" /etc/skel/.config/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/config/waybar" /etc/skel/.config/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/config/gtk-3.0" /etc/skel/.config/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/config/icons/Caelestia" /usr/share/icons/ 2>/dev/null || true
    cp "$EXTRACTED_DIR/config/aura-wallpaper.png" /usr/share/pixmaps/ 2>/dev/null || true
    echo "✓ Configuration restored"
else
    echo "⚠ No config found in backup"
fi

# ============================================
# RESTAURAR SCRIPTS
# ============================================
echo "[2/4] Restoring scripts..."
if [ -d "$EXTRACTED_DIR/scripts" ]; then
    cp -r "$EXTRACTED_DIR/scripts"/* /opt/aura/scripts/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/scripts/aura-cli.sh" /root/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/scripts/aura-voice.sh" /root/ 2>/dev/null || true
    cp -r "$EXTRACTED_DIR/scripts/aura-personalizada.sh" /root/ 2>/dev/null || true
    echo "✓ Scripts restored"
else
    echo "⚠ No scripts found in backup"
fi

# ============================================
# RESTAURAR BASE DE DATOS
# ============================================
echo "[3/4] Restoring database..."
if [ -d "$EXTRACTED_DIR/database" ]; then
    # SQLite
    find "$EXTRACTED_DIR/database" -name "*.db" -type f 2>/dev/null | while read db; do
        cp "$db" /opt/aura/ 2>/dev/null || true
    done
    
    # PostgreSQL
    if [ -f "$EXTRACTED_DIR/database/aura_db.sql" ]; then
        su - postgres -c "psql aura_db < $EXTRACTED_DIR/database/aura_db.sql" 2>/dev/null || true
    fi
    
    echo "✓ Database restored"
else
    echo "⚠ No database found in backup"
fi

# ============================================
# RESTAURAR CONFIGURACIÓN DEL SISTEMA
# ============================================
echo "[4/4] Restoring system configuration..."
if [ -d "$EXTRACTED_DIR/system" ]; then
    cp "$EXTRACTED_DIR/system/hostname" /etc/ 2>/dev/null || true
    cp "$EXTRACTED_DIR/system/hosts" /etc/ 2>/dev/null || true
    cp "$EXTRACTED_DIR/system/.env" /opt/aura/backend/ 2>/dev/null || true
    echo "✓ System configuration restored"
else
    echo "⚠ No system config found in backup"
fi

# Limpiar
rm -rf "$TEMP_DIR"

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║     Restore Complete                      ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Restored from: $BACKUP_NAME"
echo ""
echo "Next steps:"
echo "  1. Reboot: reboot"
echo "  2. Login as 'aura'"
echo "  3. Verify: curl http://localhost:8000/health"
echo ""
