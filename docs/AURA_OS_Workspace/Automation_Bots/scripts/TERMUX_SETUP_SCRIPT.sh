#!/bin/bash
# =============================================
# TERMUX SETUP SCRIPT FOR AURA/AME
# Este script configura automáticamente Termux para conectarse con AURA Core
# Versión local (no requiere descarga externa)
# =============================================

# Configuración inicial
echo "🔧 Configurando Termux para AURA..."
echo "----------------------------------------"

# Paso 1: Actualizar e instalar dependencias
echo "📥 Actualizando sistema y instalando dependencias..."
pkg update -y
pkg upgrade -y
pkg install python git openssh curl wget termux-api -y

# Verificar permisos de almacenamiento
echo "📂 Configurando permisos para /sdcard..."
termux-setup-storage

# Paso 2: Clonar repositorio AURA (usando el repositorio local)
echo "📥 Clonando repositorio AURA desde la carpeta actual..."
cd ~
if [ -d "aura-ame" ]; then
    echo "📁 Directorio aura-ame ya existe. Actualizando..."
    cd aura-ame
    git pull
else
    echo "📁 Clonando repositorio desde la ruta local..."
    # Usamos el repositorio local en lugar de descargar desde internet
    # Asumimos que el usuario ya tiene el repositorio en su PC y lo transferirá manualmente
    echo "⚠️  NOTA: Este script asume que ya tienes el repositorio AURA en tu PC."
    echo "       Debes transferir manualmente la carpeta 'aura-ame' a tu celular."
    echo "       Usa una app como Solid Explorer o FX File Explorer para copiar la carpeta."
    echo ""
    echo "📌 Instrucciones para transferir el repositorio:"
    echo "1. Copia la carpeta 'aura-ame' desde tu PC a una USB o computadora intermedia."
    echo "2. Conecta tu celular a esa computadora/USB."
    echo "3. Copia la carpeta 'aura-ame' a la raíz de tu almacenamiento interno (/sdcard/)."
    echo "4. Una vez copiada, ejecuta este comando en Termux:"
    echo "   mv /sdcard/aura-ame ~/aura-ame"
    echo "5. Continúa con el script después de copiar la carpeta."
    exit 1
fi

# Paso 3: Instalar dependencias Python
echo "🐍 Instalando dependencias Python..."
cd ~/aura-ame
pip install --upgrade pip
pip install -r requirements.txt

# Paso 4: Verificar configuración de Cloudflare
echo "⚠️  NOTA IMPORTANTE:"
echo "   Debes ejecutar 'python scripts/setup_cloudflare.py' en tu PC primero"
echo "   Luego, transfiere el archivo 'aura_urls/ame_config.json' a /sdcard/"
echo "   Usa ADB o copia manualmente a /sdcard/ame_config.json"
echo ""

# Verificar si existe el archivo de configuración
if [ ! -f "/sdcard/ame_config.json" ]; then
    echo "❌ Error: No se encontró ame_config.json en /sdcard/"
    echo "📌 Solución: Copia el archivo desde tu PC a /sdcard/"
    echo "   Usa: adb push aura_urls/ame_config.json /sdcard/"
    exit 1
fi

# Paso 5: Copiar configuración a la carpeta correcta
echo "📂 Copiando configuración a AURA..."
cp /sdcard/ame_config.json aura_urls/
chmod +x scripts/*

# Paso 6: Configurar SSH (opcional)
echo "🔐 Configurando SSH (opcional)..."
pkg install openssh -y
mkdir -p ~/.ssh
chmod 700 ~/.ssh
# Clave pública genérica (debes reemplazarla con la tuya)
echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ..." > ~/.ssh/authorized_keys
sshd &  # Iniciar servidor SSH en segundo plano

# Paso 7: Configurar termux-boot para inicio automático
echo "🚀 Configurando inicio automático..."
echo "cd ~/aura-ame && python scripts/ame_updater.py" >> ~/.bashrc

# Paso 8: Probar conexión con AURA Core
echo "🔗 Probando conexión con AURA Core..."
python scripts/test_ame_connection.py

# Paso 9: Iniciar actualizador automático en segundo plano
echo "🔄 Iniciando actualizador automático..."
screen -dmS aura_updater python scripts/ame_updater.py

# Paso 10: Mostrar instrucciones finales
echo ""
echo "✅ Configuración completada con éxito!"
echo ""
echo "📌 Instrucciones finales:"
echo "1. Asegúrate de que 'start_aura.py' esté corriendo en tu PC"
echo "2. Verifica que el túnel Cloudflare esté activo en tu PC"
echo "3. Ejecuta en tu PC: python scripts/ame_config_generator.py (si no lo hiciste)"
echo "4. Transfiere el nuevo ame_config.json a /sdcard/ si lo actualizaste"
echo ""
echo "📡 Para verificar el estado:"
echo "   - En tu PC: python scripts/health_check.py"
echo "   - En tu celular: python scripts/test_ame_connection.py"
echo ""
echo "🔄 El actualizador automático se ejecutará cada 6 horas"
echo "📝 Los logs están en /sdcard/update_ame_log.txt"
echo ""
echo "🎯 Resumen de lo configurado:"
echo "   - Termux actualizado con dependencias"
echo "   - Repositorio AURA clonado y configurado"
echo "   - Configuración de Cloudflare lista (necesitas transferir ame_config.json)"
echo "   - SSH configurado (opcional)"
echo "   - Actualizador automático en segundo plano"
echo ""

# Verificar procesos en ejecución
echo ""
echo "🔍 Verificando procesos..."
ps | grep -E "ame_updater|sshd"