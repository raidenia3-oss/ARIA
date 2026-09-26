#!/bin/bash

# Script de auto-diagnóstico para el ecosistema AURA
# Verifica el estado crítico del entorno

# Función para verificar ADB
check_adb() {
    echo "Verificando disponibilidad de ADB..."
    if command -v adb &> /dev/null; then
        echo "✅ ADB está disponible en el PATH."
        adb_version=$(adb --version)
        echo "Versión de ADB: $adb_version"
    else
        echo "❌ ADB no está disponible en el PATH."
        adb_path=$(where adb 2>/dev/null || which adb 2>/dev/null)
        if [ -n "$adb_path" ]; then
            echo "Posible ruta de ADB: $adb_path"
        else
            echo "No se encontró ADB en el sistema."
        fi
    fi
}

# Función para verificar el estado del servidor Hugging Face
check_huggingface() {
    echo -e "\nVerificando estado del servidor Hugging Face..."
    SERVER_URL="https://raiden456-slut.hf.space/health"
    if curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL" | grep -q "200"; then
        echo "✅ Servidor Hugging Face responde correctamente (HTTP 200)."
    else
        echo "❌ El servidor Hugging Face no responde correctamente."
        curl -v "$SERVER_URL"
    fi
}

# Función para verificar el entorno virtual de Python
check_python_env() {
    echo -e "\nVerificando entorno virtual de Python..."
    if [ -d ".venv-3" ]; then
        echo "✅ Directorio .venv-3 existe."
        if command -v python &> /dev/null; then
            echo "✅ Python está disponible en el PATH."
            python_version=$(python --version)
            echo "Versión de Python: $python_version"

            # Activar entorno virtual y probar importaciones críticas
            echo "Activando entorno virtual y probando importaciones..."
            source .venv-3/bin/activate
            if python -c "import sys; print(f'Entorno virtual activado: {sys.prefix}')"; then
                echo "✅ Entorno virtual activado correctamente."

                # Probar importaciones críticas
                if python -c "import requests; print('✅ requests importado correctamente')"; then
                    echo "✅ Módulo requests disponible."
                else
                    echo "❌ Error al importar requests."
                fi

                if python -c "import opencv-python; print('✅ opencv-python importado correctamente')"; then
                    echo "✅ Módulo opencv-python disponible."
                else
                    echo "❌ Error al importar opencv-python."
                fi

                if python -c "import pyautogui; print('✅ pyautogui importado correctamente')"; then
                    echo "✅ Módulo pyautogui disponible."
                else
                    echo "❌ Error al importar pyautogui."
                fi

                if python -c "import flet; print('✅ flet importado correctamente')"; then
                    echo "✅ Módulo flet disponible."
                else
                    echo "❌ Error al importar flet."
                fi
            else
                echo "❌ No se pudo activar el entorno virtual."
            fi
        else
            echo "❌ Python no está disponible en el PATH."
        fi
    else
        echo "❌ Directorio .venv-3 no encontrado."
    fi
}

# Función principal
main() {
    echo "============================================="
    echo "🔍 AURA Auto-Diagnostic Tool"
    echo "============================================="
    echo ""

    check_adb
    check_huggingface
    check_python_env

    echo -e "\n============================================="
    echo "📋 Diagnóstico completado."
    echo "============================================="
}

main
