import subprocess
import sys
import os
import json
import shutil
from datetime import datetime

PROJECT = r"C:\Users\User\Downloads\AURA"
ANDROID = os.path.join(PROJECT, "android")

def bump_version():
    """Incrementa la versión automáticamente"""
    pkg_path = os.path.join(PROJECT, "package.json")
    with open(pkg_path) as f:
        pkg = json.load(f)
    parts = pkg["version"].split(".")
    parts[2] = str(int(parts[2]) + 1)
    pkg["version"] = ".".join(parts)
    with open(pkg_path, "w") as f:
        json.dump(pkg, f, indent=2)
    print(f"📦 Nueva versión: {pkg['version']}")
    return pkg["version"]

def build_web():
    """Compila el frontend web"""
    print("🔨 Compilando web...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=PROJECT,
        shell=True
    )
    if result.returncode != 0:
        print("❌ Error en build web")
        sys.exit(1)
    print("✅ Build web OK")

def sync_capacitor():
    """Sincroniza el build con Android"""
    print("🔄 Sincronizando Capacitor...")
    subprocess.run(["npx", "capacitor", "sync", "android"],
                   cwd=PROJECT, shell=True)
    print("✅ Sync OK")

def build_apk(release=False):
    """Compila el APK"""
    print(f"📱 Compilando APK {'release' if release else 'debug'}...")
    task = "assembleRelease" if release else "assembleDebug"
    result = subprocess.run(
        [r".\gradlew.bat", task],
        cwd=ANDROID,
        shell=True
    )
    if result.returncode == 0:
        apk_dir = os.path.join(
            ANDROID, "app", "build", "outputs", "apk",
            "release" if release else "debug"
        )
        for f in os.listdir(apk_dir):
            if f.endswith(".apk"):
                apk_path = os.path.join(apk_dir, f)
                out = os.path.join(PROJECT, "output",
                                   f"AME_{datetime.now():%Y%m%d_%H%M}.apk")
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copy(apk_path, out)
                print(f"✅ APK: {out}")
                return out
    else:
        print("❌ Error compilando APK")
        return None

def deploy_ota():
    """Despliega actualización OTA"""
    print("🚀 Desplegando OTA...")
    dist = os.path.join(PROJECT, "dist")

    version_info = {
        "version": json.load(open(os.path.join(PROJECT, "package.json")))["version"],
        "timestamp": datetime.now().isoformat(),
        "changelog": "Actualización automática AURA/AME"
    }
    with open(os.path.join(dist, "version.json"), "w") as f:
        json.dump(version_info, f, indent=2)

    print("✅ Configuración de OTA lista. Sube manualmente a GitHub Pages.")

def send_update_command():
    """Dice a AURA que notifique a AME que hay update"""
    import asyncio
    import websockets
    import json

    async def notify():
        try:
            async with websockets.connect(
                "ws://localhost:8765", open_timeout=5
            ) as ws:
                await ws.send(json.dumps({
                    "node": "DEPLOY_SCRIPT",
                    "event": "AURA_COMMAND",
                    "payload": {"command": "UPDATE_NOW"}
                }))
                print("📨 AURA notificado — AME actualizará pronto")
        except Exception as e:
            print(f"⚠️  AURA Core no está corriendo: {e}")

    asyncio.run(notify())

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "ota"

    if mode == "ota":
        print("=== DEPLOY OTA (sin reinstalar APK) ===")
        build_web()
        deploy_ota()
        send_update_command()

    elif mode == "apk":
        print("=== BUILD APK COMPLETO ===")
        version = bump_version()
        build_web()
        sync_capacitor()
        apk = build_apk(release=False)
        if apk:
            print(f"\n✅ APK listo: {apk}")
            print("📲 Instala manualmente o usa ADB:")
            print(f"   adb install -r {apk}")

    elif mode == "full":
        print("=== DEPLOY COMPLETO ===")
        version = bump_version()
        build_web()
        sync_capacitor()
        build_apk(release=False)
        deploy_ota()
        send_update_command()

    else:
        print("Modos disponibles: ota, apk, full")