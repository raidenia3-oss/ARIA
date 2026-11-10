#!/usr/bin/env bash
# asagi-link: localiza/wait para adb y espera a que aparezca un dispositivo Android.
# Uso: ./tools/asagi_link.sh   (Git Bash)
# - Localiza ~/platform-tools/adb.exe; si falta, lo descarga de dl.google.com.
# - Espera `adb devices` hasta ver un dispositivo en estado 'device'.
# - Idempotente: si ya hay un dispositivo, imprime estado y sale.
set -uo pipefail

ADB="$HOME/platform-tools/adb.exe"
ZIP="$HOME/platform-tools-latest-windows.zip"
URL="https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

log() { printf '[asagi-link] %s\n' "$*"; }

# ---------- 1. Localizar/instalar adb ----------
if [ ! -x "$ADB" ]; then
  log "adb no encontrado en $ADB; descargando platform-tools..."
  if ! command -v curl >/dev/null 2>&1; then
    log "ERROR: curl no disponible para descargar platform-tools"
    exit 1
  fi
  if ! curl -fL -o "$ZIP" "$URL" 2>/dev/null; then
    log "ERROR: fallo la descarga de platform-tools desde $URL"
    exit 1
  fi
  if command -v unzip >/dev/null 2>&1; then
    unzip -o -q "$ZIP" -d "$HOME" || { log "ERROR: fallo la extraccion de platform-tools"; exit 1; }
  else
    powershell.exe -NoProfile -Command "Expand-Archive -Path '$ZIP' -DestinationPath '$HOME' -Force" \
      || { log "ERROR: fallo la extraccion de platform-tools"; exit 1; }
  fi
  rm -f "$ZIP"
fi
if [ ! -x "$ADB" ]; then
  log "ERROR: no se pudo localizar adb en $ADB"
  exit 1
fi
log "adb listo: $ADB"

# ---------- 2. Esperar dispositivo ----------
log "Esperando dispositivo Android (conecta por USB con depuracion USB activa)..."
while true; do
  if "$ADB" devices 2>/dev/null | grep -Eq '\tdevice$'; then
    log "Dispositivo detectado:"
    "$ADB" devices 2>/dev/null | grep -E '\tdevice$'
    exit 0
  fi
  sleep 5
done
