#!/usr/bin/env bash
set -euo pipefail
GODOT_PATH="${GODOT_PATH:-godot}"
if [[ $# -lt 1 ]]; then
  echo "Uso: build_godot.sh [windows|linux|mac|android]"
  exit 1
fi
TARGET="$1"
echo "Building AURA Desktop for ${TARGET}..."
case "${TARGET}" in
  windows)
    "${GODOT_PATH}" --export "Windows Desktop" --headless
    ;;
  linux)
    "${GODOT_PATH}" --export "Linux" --headless
    ;;
  mac)
    "${GODOT_PATH}" --export "macOS" --headless
    ;;
  android)
    "${GODOT_PATH}" --export "Android" --headless
    ;;
  *)
    echo "Target no soportado: ${TARGET}"
    exit 1
    ;;
esac
echo "Build completado."
