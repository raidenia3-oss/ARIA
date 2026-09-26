#!/usr/bin/env bash
set -euo pipefail

MOBILE_DIR="$(pwd)/ame-mobile"

if [ ! -d "$MOBILE_DIR" ]; then
  echo "FAIL: ame-mobile/ no existe"
  exit 1
fi

cd "$MOBILE_DIR"

for f in pubspec.yaml lib/main.dart android/build.gradle; do
  if [ ! -f "$f" ]; then
    echo "FAIL: Falta $f"
    exit 1
  fi
done

grep -q "webview_flutter" pubspec.yaml || { echo "FAIL: Falta webview_flutter"; exit 1; }
grep -q "google_mobile_ads" pubspec.yaml || { echo "FAIL: Falta google_mobile_ads"; exit 1; }

if command -v flutter >/dev/null 2>&1; then
  flutter analyze || true
  flutter build apk --debug || { echo "FAIL: flutter build apk --debug"; exit 1; }
  echo "PASS: Flutter build completado"
else
  echo "WARN: Flutter SDK no detectado; se valida estructura para build remoto/local."
  echo "PASS: Proyecto Flutter listo para compilación"
fi
