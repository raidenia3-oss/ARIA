#!/bin/bash
#
# Script para configurar el entorno en Termux para AME
#

# Configuración
PROJECT_DIR="$HOME/AME-termux"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_DIR="$PROJECT_DIR/logs"

# Función para verificar si un comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verificar y actualizar paquetes
echo "Actualizando paquetes..."
pkg update -y

# Instalar Python si no está instalado
if ! command_exists python; then
    echo "Instalando Python..."
    pkg install -y python
fi

# Crear directorios necesarios
echo "Creando directorios..."
mkdir -p "$PROJECT_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$SCRIPTS_DIR"

# Copiar scripts desde la carpeta local (si están disponibles)
echo "Copiando scripts..."
if [ -d "/data/data/com.termux/files/home/AME-termux/scripts" ]; then
    cp /data/data/com.termux/files/home/AME-termux/scripts/simple_termux_watcher.py "$PROJECT_DIR/"
    cp /data/data/com.termux/files/home/AME-termux/scripts/start_termux_server.sh "$PROJECT_DIR/"
fi

# Dar permisos de ejecución
echo "Configurando permisos..."
chmod +x "$PROJECT_DIR/simple_termux_watcher.py"
chmod +x "$PROJECT_DIR/start_termux_server.sh"

# Configurar el script de inicio automático
echo "Configurando script de inicio automático..."
if ! grep -q "AME-termux" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Inicio automático de AME" >> ~/.bashrc
    echo "if [ -f \"$HOME/AME-termux/start_termux_server.sh\" ]; then" >> ~/.bashrc
    echo "  $HOME/AME-termux/start_termux_server.sh" >> ~/.bashrc
    echo "fi" >> ~/.bashrc
    echo "Script de inicio configurado en ~/.bashrc"
else
    echo "Script de inicio ya configurado."
fi

echo ""
echo "Configuración completada. Ejecuta:"
echo "  source ~/.bashrc"
echo "para aplicar los cambios."
echo ""
echo "Luego ejecuta manualmente:"
echo "  $HOME/AME-termux/start_termux_server.sh"
echo "para iniciar el servidor y el watcher."