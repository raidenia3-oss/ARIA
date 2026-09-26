#!/bin/bash
#
# setup_venice_modules.sh - Script para configurar la estructura de módulos Venice en Termux.
# Este script debe ejecutarse en el dispositivo móvil (Termux) para preparar el entorno.
#

# Configuración
MODULES_DIR="/sdcard/venice_modules"
LAUNCHER_SCRIPT="venice_launcher.py"
LOG_FILE="/sdcard/venice_launcher.log"
AURA_DIR="$HOME/.aura"

# Función para verificar si termux-setup-storage está configurado
check_storage_permission() {
    if ! termux-setup-storage --list | grep -q "/sdcard"; then
        echo "⚠️  Advertencia: No se tiene acceso a /sdcard."
        echo "   Ejecute 'termux-setup-storage' para permitir el acceso a almacenamiento externo."
        return 1
    fi
    return 0
}

# Función para crear directorios
create_directories() {
    echo "📁 Creando directorios necesarios..."

    # Crear directorio principal de módulos
    if [ ! -d "$MODULES_DIR" ]; then
        mkdir -p "$MODULES_DIR"
        echo "   ✅ Directorio de módulos creado: $MODULES_DIR"
    else
        echo "   ✅ Directorio de módulos ya existe: $MODULES_DIR"
    fi

    # Crear directorio para logs
    if [ ! -d "$(dirname "$LOG_FILE")" ]; then
        mkdir -p "$(dirname "$LOG_FILE")"
    fi

    # Crear directorio para AURA (si no existe)
    if [ ! -d "$AURA_DIR" ]; then
        mkdir -p "$AURA_DIR"
        echo "   ✅ Directorio de AURA creado: $AURA_DIR"
    else
        echo "   ✅ Directorio de AURA ya existe: $AURA_DIR"
    fi
}

# Función para transferir el launcher
transfer_launcher() {
    echo "🚀 Transferiendo Venice Launcher..."

    # Verificar si el script ya existe
    if [ -f "$AURA_DIR/$LAUNCHER_SCRIPT" ]; then
        echo "   ✅ El launcher ya existe en $AURA_DIR/$LAUNCHER_SCRIPT"
        return
    fi

    # Intentar transferir desde la PC (asumiendo que está en el directorio actual de la PC)
    echo "   🔍 Buscando launcher en la PC..."
    if command -v scp &> /dev/null; then
        # Intentar transferir desde la PC (asumiendo que el usuario está en la PC)
        echo "   📤 Intentando transferir desde la PC..."
        if scp -P 2222 "$LAUNCHER_SCRIPT" user@localhost:"$AURA_DIR/" > /dev/null 2>&1; then
            echo "   ✅ Launcher transferido exitosamente desde la PC"
            return
        else
            echo "   ❌ No se pudo transferir desde la PC. Intentando con otro método..."
        fi
    fi

    # Si no se pudo transferir desde la PC, crear un launcher básico
    echo "   📝 Creando launcher básico localmente..."
    cat > "$AURA_DIR/$LAUNCHER_SCRIPT" << 'EOL'
#!/usr/bin/env python3
"""
Venice Launcher - Versión básica para dispositivos móviles
Este launcher es una versión reducida para cuando no se puede transferir el launcher completo.
"""

import os
import sys
import subprocess
import json
import time

def execute_module(module_path, args):
    try:
        command = [sys.executable, module_path] + args
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "status": "success",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "Uso: python venice_launcher.py <módulo> [args...]", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}))
        sys.exit(1)

    module_path = sys.argv[1]
    args = sys.argv[2:]

    # Asegurar que el módulo esté en el directorio correcto
    modules_dir = "/sdcard/venice_modules"
    if not os.path.isabs(module_path):
        module_path = os.path.join(modules_dir, module_path)

    if not os.path.isfile(module_path):
        print(json.dumps({"status": "error", "message": f"Módulo no encontrado: {module_path}", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}))
        sys.exit(1)

    result = execute_module(module_path, args)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
EOL

    echo "   ✅ Launcher básico creado en $AURA_DIR/$LAUNCHER_SCRIPT"
}

# Función para configurar permisos
set_permissions() {
    echo "🔒 Configurando permisos..."

    # Dar permisos de ejecución al launcher
    chmod +x "$AURA_DIR/$LAUNCHER_SCRIPT"

    # Asegurar que el directorio de módulos tenga permisos correctos
    chmod -R 755 "$MODULES_DIR"

    echo "   ✅ Permisos configurados correctamente"
}

# Función para crear un módulo de ejemplo
create_example_module() {
    echo "📝 Creando módulo de ejemplo..."

    EXAMPLE_MODULE="$MODULES_DIR/example_module.py"

    cat > "$EXAMPLE_MODULE" << 'EOL'
#!/usr/bin/env python3
"""
Ejemplo de módulo Venice.
Este módulo demuestra cómo crear un módulo para el sistema Venice.
"""

import sys
import time

def main():
    print("🚀 Ejecutando módulo de ejemplo Venice")
    print(f"   Hora de ejecución: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Argumentos recibidos: {sys.argv[1:]}")

    # Simular algún trabajo
    time.sleep(1)

    print("   ✅ Módulo de ejemplo completado exitosamente")
    print(f"   Valor de retorno: 0")

if __name__ == "__main__":
    main()
EOL

    chmod +x "$EXAMPLE_MODULE"
    echo "   ✅ Módulo de ejemplo creado: $EXAMPLE_MODULE"
}

# Función para configurar el entorno de Python
setup_python_environment() {
    echo "🐍 Configurando entorno de Python..."

    # Verificar que Python esté instalado
    if ! command -v python &> /dev/null; then
        echo "   ❌ Python no está instalado. Instalándolo..."
        pkg install python -y
    fi

    # Verificar que pip esté disponible
    if ! command -v pip &> /dev/null; then
        echo "   ❌ pip no está disponible. Instalándolo..."
        pkg install python-pip -y
    fi

    # Instalar dependencias básicas si no están presentes
    if ! pip list | grep -q "requests"; then
        echo "   📦 Instalando dependencias de Python..."
        pip install requests
    fi

    echo "   ✅ Entorno de Python configurado correctamente"
}

# Función principal
main() {
    echo "🔧 Configurando estructura de módulos Venice en Termux"
    echo "==================================================="

    # Verificar permisos de almacenamiento
    if ! check_storage_permission; then
        echo ""
        echo "⚠️  No se puede continuar sin permisos de almacenamiento."
        echo "    Por favor, ejecute 'termux-setup-storage' y vuelva a intentar."
        exit 1
    fi

    # Crear directorios
    create_directories

    # Configurar entorno de Python
    setup_python_environment

    # Transferir launcher
    transfer_launcher

    # Configurar permisos
    set_permissions

    # Crear módulo de ejemplo
    create_example_module

    echo ""
    echo "🎉 Configuración completada exitosamente!"
    echo ""
    echo "Resumen:"
    echo "   - Directorio de módulos: $MODULES_DIR"
    echo "   - Launcher: $AURA_DIR/$LAUNCHER_SCRIPT"
    echo "   - Módulo de ejemplo: $MODULES_DIR/example_module.py"
    echo ""
    echo "Próximos pasos:"
    echo "   1. Transfiera módulos adicionales a $MODULES_DIR"
    echo "   2. Ejecute el launcher con: python $AURA_DIR/$LAUNCHER_SCRIPT <módulo> [args]"
    echo "   3. Para pruebas, ejecute: python $AURA_DIR/$LAUNCHER_SCRIPT example_module.py"
}

# Ejecutar función principal
main