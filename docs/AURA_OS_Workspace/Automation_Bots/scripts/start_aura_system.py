"""
Script para iniciar todo el sistema AURA:
1. Watchdog de Rollercoin (automatización)
2. Backend FastAPI
3. Verificación de emulador (opcional)
"""

import subprocess
import os
import sys
import time
import threading
import signal
from pathlib import Path


def start_rollercoin_watchdog():
    """Inicia el watchdog de Rollercoin en segundo plano"""
    watchdog_script = Path(__file__).resolve().parent / "rollercoin_watchdog.py"
    try:
        print("🤖 Iniciando watchdog de Rollercoin...")
        process = subprocess.Popen(
            [sys.executable, str(watchdog_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print("✅ Watchdog de Rollercoin iniciado correctamente")
        return process
    except Exception as e:
        print(f"❌ Error al iniciar watchdog de Rollercoin: {e}")
        return None


def start_backend_server():
    """Inicia el backend FastAPI en segundo plano"""
    venv_path = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
    try:
        print("🚀 Iniciando backend FastAPI...")
        process = subprocess.Popen(
            [
                str(venv_path),
                "-m",
                "uvicorn",
                "core.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "5000",
                "--reload",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path(__file__).resolve().parent),
        )
        print("✅ Backend FastAPI iniciado correctamente")
        return process
    except Exception as e:
        print(f"❌ Error al iniciar backend: {e}")
        return None


def check_emulator():
    """Verifica si hay un emulador abierto"""
    try:
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)

        devices = []
        for line in result.stdout.splitlines()[1:]:  # Saltar la primera línea
            if line.strip() and "device" in line.lower():
                device = line.split()[0]
                devices.append(device)

        if devices:
            print(f"📱 Emulador detectado: {devices[0]}")
            print("✅ El sistema está listo para instalar la app en el emulador")
        else:
            print("⚠️  No se detectó ningún emulador abierto")
            print("   Puedes instalar manualmente el APK en un emulador o dispositivo físico")

        return devices
    except Exception as e:
        print(f"⚠️  Error al verificar emulador: {e}")
        return []


def main():
    print("=" * 60)
    print("🔥 AURA SYSTEM STARTER — INICIANDO TODO EL SISTEMA")
    print("=" * 60)
    print("📌 Este script inicia:")
    print("   1. Watchdog de Rollercoin (automatización)")
    print("   2. Backend FastAPI")
    print("   3. Verifica emulador (opcional)")
    print("=" * 60)

    # Iniciar procesos en hilos separados
    processes = []

    # 1. Iniciar watchdog de Rollercoin
    watchdog_process = start_rollercoin_watchdog()
    if watchdog_process:
        processes.append(watchdog_process)

    # 2. Iniciar backend
    backend_process = start_backend_server()
    if backend_process:
        processes.append(backend_process)

    # 3. Verificar emulador
    check_emulator()

    print("\n" + "=" * 60)
    print("🎉 SISTEMA AURA INICIADO CON ÉXITO")
    print("✅ Watchdog de Rollercoin corriendo")
    print("✅ Backend FastAPI en http://localhost:5000")
    print("=" * 60)
    print("💡 Instrucciones:")
    print("   1. Usa el pipeline de despliegue para compilar e instalar en el emulador:")
    print("      python core/deploy_pipeline.py")
    print("   2. Monitorea los logs en la consola")
    print("   3. Presiona Ctrl+C para detener todos los servicios")
    print("=" * 60)

    # Esperar a que el usuario presione Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo todos los servicios...")
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        print("👋 ¡Hasta luego!")


if __name__ == "__main__":
    main()
