#!/bin/bash

# Script para compilar APK de AURA Mobile usando Capacitor
# Requiere Android SDK y herramientas de build instaladas

# Configuración
APP_NAME="AURA Mobile"
BUILD_DIR="dist/android/app/build/outputs/apk/release"
APK_OUTPUT="$BUILD_DIR/app-release.apk"

# Verificar dependencias
if ! command -v gradlew &> /dev/null; then
    echo "Error: gradlew no encontrado. Asegúrate de estar en el directorio del proyecto."
    exit 1
fi

# Limpiar build anterior
echo "Limpiando build anterior..."
./gradlew clean

# Configurar endpoint del Cloudflare Tunnel en el código web
echo "Configurando endpoint del Cloudflare Tunnel..."
sed -i 's|const apiEndpoint =.*|const apiEndpoint = "https://tunel-aura.trycloudflare.com/api/mobile-protocol";|g' ../AME_Core/dashboard.html

# Sincronizar archivos web con Capacitor
echo "Sincronizando archivos web..."
npx cap sync android

# Compilar APK en modo release
echo "Compilando APK en modo release..."
./gradlew assembleRelease

# Verificar salida del APK
if [ -f "$APK_OUTPUT" ]; then
    echo "APK generado exitosamente en: $APK_OUTPUT"
    echo "Puedes instalarlo en tu dispositivo Android con:"
    echo "adb install $APK_OUTPUT"
else
    echo "Error: No se pudo generar el APK. Revisa los logs de compilación."
    exit 1
fi