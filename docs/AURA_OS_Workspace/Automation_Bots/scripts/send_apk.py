#!/usr/bin/env python3
"""
send_apk.py — Compila APK y envía link por WhatsApp (CallMeBot)
Uso: python scripts/send_apk.py
"""

import subprocess, os, sys, glob, json, urllib.request, urllib.parse, time
from pathlib import Path

PHONE = "+51942858492"
API_KEY = "6272348"
AURA_DIR = r"C:\Users\User\Downloads\AURA"
ANDROID_DIR = os.path.join(AURA_DIR, "android")
OUTPUT_DIR = os.path.join(AURA_DIR, "output")
GRADLEW = os.path.join(ANDROID_DIR, "gradlew.bat")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def log(msg):
    print(f"[send_apk] {msg}")


def build_apk():
    """Compila APK debug con Gradle"""
    log("Compilando APK debug...")
    start = time.time()
    result = subprocess.run(
        [GRADLEW, "assembleDebug"],
        cwd=ANDROID_DIR,
        capture_output=True, text=True, shell=True
    )
    elapsed = round(time.time() - start)

    if result.returncode != 0:
        log(f"Build falló ({elapsed}s)")
        log(result.stderr[-2000:])
        return None

    # Buscar APK generado
    pattern = os.path.join(
        ANDROID_DIR, "app", "build", "outputs", "apk", "debug", "*.apk"
    )
    apks = glob.glob(pattern)
    if not apks:
        log("No se encontró APK en outputs")
        return None

    apk_path = max(apks, key=os.path.getmtime)
    size_mb = os.path.getsize(apk_path) / (1024 * 1024)
    log(f"APK compilado en {elapsed}s: {size_mb:.1f}MB")

    # Copiar a output/
    dest = os.path.join(OUTPUT_DIR, f"AME_debug_latest.apk")
    import shutil
    shutil.copy(apk_path, dest)
    log(f"Copiado a: {dest}")
    return dest


def upload_to_fileio(apk_path):
    """Sube el APK a file.io y devuelve el link"""
    log("Subiendo APK a file.io...")
    import requests

    with open(apk_path, "rb") as f:
        r = requests.post(
            "https://file.io",
            files={"file": f},
            params={"expires": "1"}
        )
    if r.status_code == 200:
        data = r.json()
        if data.get("success"):
            link = data["link"]
            log(f"Link generado: {link}")
            return link
        log(f"file.io error: {data}")
    else:
        log(f"file.io HTTP {r.status_code}: {r.text}")
    return None


def send_whatsapp(message):
    """Envía mensaje por WhatsApp via CallMeBot"""
    log("Enviando mensaje por WhatsApp...")
    params = urllib.parse.urlencode({
        "phone": PHONE,
        "text": message,
        "apikey": API_KEY
    })
    url = f"https://api.callmebot.com/whatsapp.php?{params}"

    try:
        r = urllib.request.urlopen(url, timeout=30)
        log(f"WhatsApp respuesta: {r.read().decode()[:200]}")
        return True
    except Exception as e:
        log(f"Error WhatsApp: {e}")
        return False


def main():
    log("=== Inicio del proceso ===")

    # 1. Compilar APK
    apk_path = build_apk()
    if not apk_path:
        log("❌ Compilación fallida")
        sys.exit(1)

    # 2. Subir a file.io
    link = upload_to_fileio(apk_path)
    if not link:
        log("❌ Subida a file.io fallida")
        # Intentar enviar mensaje de error
        send_whatsapp("❌ Error subiendo APK a file.io")
        sys.exit(1)

    # 3. Enviar link por WhatsApp
    size_mb = os.path.getsize(apk_path) / (1024 * 1024)
    message = (
        f"✅ APK listo. Descarga e instala: {link}\n"
        f"Válido para 1 descarga. Tamaño: {size_mb:.1f} MB"
    )
    if send_whatsapp(message):
        log("✅ Mensaje enviado por WhatsApp")
    else:
        log("❌ Error enviando WhatsApp")
        sys.exit(1)

    log("=== Proceso completado ===")


if __name__ == "__main__":
    main()