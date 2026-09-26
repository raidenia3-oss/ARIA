#!/usr/bin/env python3
"""
AURA DEPLOY PIPELINE v3 — Compilación + Despliegue en Emulador Local + Watchdog
==========================================================================
Pilar #1: Sin cables físicos — todo via ADB local (puertos 5554-5559)
Pilar #2: Auto-detección de emuladores (Android Studio, BlueStacks, LDPlayer)
Pilar #3: Watchdog de ecosistema (FastAPI + Rollercoin + IA)

Flujo:
  1. Configurar urls.xml para 10.0.2.2:5000
  2. Compilar APK con Gradle clean assembleDebug
  3. Escanear puertos ADB de emuladores locales
  4. Instalar APK en el emulador detectado
  5. Lanzar la app en el emulador
  6. Arrancar servidor FastAPI
  7. Iniciar Watchdog de ecosistema
"""

import subprocess
import os
import sys
import socket
import time
import threading
import json
import shutil
import platform
import signal
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

# ─── Configuración de colores ANSI ───
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log(msg: str, level: str = "info"):
    """Logging con colores."""
    prefix = {
        "ok": f"{GREEN}[✓]{RESET}",
        "warn": f"{YELLOW}[⚠]{RESET}",
        "error": f"{RED}[✗]{RESET}",
        "info": f"{CYAN}[⟳]{RESET}",
        "bold": f"{BOLD}[⟁]{RESET}",
    }.get(level, "[?]")
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{ts} {prefix} {msg}")


# ─── Constantes ───
PROJECT_DIR = Path(__file__).resolve().parent.parent / "AME_ECOSYSTEM" / "ame_app_android"
GRADLEW_BAT = PROJECT_DIR / "gradlew.bat"
APK_OUTPUT = PROJECT_DIR / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
DEST_APK = Path.home() / "Desktop" / "AURA-INSTALAME.apk"
VENV_PYTHON = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
URLS_XML = PROJECT_DIR / "app" / "src" / "main" / "res" / "values" / "urls.xml"
BACKEND_PORT = 5000

# Puertos de emuladores Android comunes (ADB)
EMULATOR_PORTS = list(range(5554, 5560))  # 5554–5559

# Rutas de ADB conocidas
ADB_PATHS = [
    Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe",
    Path("C:/Program Files/BlueStacks_nxt/HD-Adb.exe"),
    Path("C:/Program Files/LDPlayer9/adb.exe"),
    Path("C:/Program Files/BlueStacks/HD-Adb.exe"),
    Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb",
]

PKG_NAME = "com.ame.ecosystem"
MAIN_ACTIVITY = ".MainActivity"


# ─── Detección de Java ───
def detect_java_home() -> Optional[str]:
    """Detecta JAVA_HOME automáticamente."""
    candidates = [
        r"C:\Program Files\Eclipse Adoptium\jdk-11.0.31.11-hotspot",
        r"C:\Program Files\Java\jdk-11.0.22+7",
        r"C:\Program Files\AdoptOpenJDK\jdk-11.0.14+9",
        r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot",
        r"C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot",
    ]
    for path in candidates:
        if os.path.exists(path) and os.path.isdir(path):
            return path

    # Buscar en %PROGRAMFILES%
    for root in [r"C:\Program Files\Eclipse Adoptium", r"C:\Program Files\Java"]:
        if os.path.exists(root):
            for d in os.listdir(root):
                full = os.path.join(root, d)
                if os.path.isdir(full) and ("jdk" in d.lower() or "jre" in d.lower()):
                    return full
    return None


# ─── ADB Utils ───
def find_adb() -> Optional[Path]:
    """Encontrar ADB en rutas conocidas."""
    for p in ADB_PATHS:
        if p.exists():
            return p

    # Buscar en PATH
    try:
        result = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip().split("\n")[0]
            return Path(path)
    except:
        pass
    return None


def adb_command(args: List[str], timeout: int = 10) -> Tuple[str, int]:
    """Ejecutar comando ADB."""
    adb = find_adb()
    if not adb:
        return "ADB no encontrado", -1
    try:
        result = subprocess.run([str(adb)] + args, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return f"ERROR: {e}", -1


def scan_emulator_ports() -> List[str]:
    """
    Escanear puertos ADB de emuladores locales (5554-5559).
    No requiere cables físicos — solo conexión TCP local.
    """
    devices = []
    log("Escaneando puertos de emuladores locales...", "info")

    for port in EMULATOR_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                # Conectar ADB al emulador
                out, code = adb_command(["connect", f"127.0.0.1:{port}"], timeout=3)
                devices.append(f"127.0.0.1:{port}")
                log(f"  Puerto {port} → Emulador detectado", "ok")
            sock.close()
        except:
            pass
        finally:
            sock.close()

    # También verificar con adb devices
    out, code = adb_command(["devices"], timeout=5)
    if code == 0:
        for line in out.splitlines()[1:]:
            if line.strip() and "device" in line.lower():
                dev = line.split()[0]
                if dev not in devices:
                    devices.append(dev)

    return devices


# ─── Configuración de URLs ───
def update_urls_xml():
    """Actualizar urls.xml para que apunte al backend del host."""
    backend_url = "http://10.0.2.2:5000"

    if not URLS_XML.exists():
        URLS_XML.parent.mkdir(parents=True, exist_ok=True)
        content = f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="backend_url">{backend_url}</string>
</resources>"""
        URLS_XML.write_text(content, encoding="utf-8")
        log(f"urls.xml creado con URL={backend_url}", "ok")
        return True

    content = URLS_XML.read_text(encoding="utf-8")
    if backend_url in content:
        log(f"urls.xml OK: {backend_url}", "ok")
        return True

    # Actualizar
    import re

    new_content = re.sub(
        r'<string name="backend_url">.*?</string>',
        f'<string name="backend_url">{backend_url}</string>',
        content,
    )
    URLS_XML.write_text(new_content, encoding="utf-8")
    log(f"urls.xml actualizado a {backend_url}", "ok")
    return True


# ─── Compilación ───
def build_apk():
    """Compilar APK con Gradle clean + assembleDebug."""
    log("🔧 Compilando APK...", "bold")

    if not update_urls_xml():
        log("No se pudo configurar urls.xml", "warn")

    java_home = detect_java_home()
    if not java_home:
        log("JAVA_HOME no detectado. Instala JDK 11+", "error")
        return False

    env = os.environ.copy()
    env["JAVA_HOME"] = java_home

    cmd = [str(GRADLEW_BAT), "clean", "assembleDebug"]
    log(f"Ejecutando: {' '.join(cmd[-3:])} con JAVA_HOME={java_home}", "info")

    try:
        result = subprocess.run(
            cmd, cwd=str(PROJECT_DIR), capture_output=True, text=True, timeout=1200, env=env
        )

        if result.returncode != 0:
            # Mostrar últimas líneas de error
            lines = result.stdout.split("\n") + result.stderr.split("\n")
            errors = [
                l for l in lines if any(x in l.lower() for x in ["error", "fail", "exception"])
            ]
            for e in errors[-5:]:
                log(e.strip()[:200], "error")
            return False

        if APK_OUTPUT.exists():
            size_mb = APK_OUTPUT.stat().st_size / (1024 * 1024)
            log(f"APK compilado: {size_mb:.1f} MB", "ok")
            # Copiar al escritorio
            shutil.copy2(APK_OUTPUT, DEST_APK)
            log(f"APK copiado a: {DEST_APK}", "ok")
            return True
        else:
            log(f"APK no encontrado en {APK_OUTPUT}", "error")
            return False

    except subprocess.TimeoutExpired:
        log("Timeout en compilación (1200s)", "error")
        return False
    except Exception as e:
        log(f"Error en compilación: {e}", "error")
        return False


# ─── Instalación en Emulador ───
def install_and_launch_on_emulator():
    """Instalar APK y lanzar app en el emulador detectado."""
    log("📱 Buscando emulador local...", "bold")

    devices = scan_emulator_ports()
    if not devices:
        log("No se encontraron emuladores. Abre Android Studio/BlueStacks/LDPlayer", "warn")
        log("Continuando solo con backend...", "warn")
        return False

    device = devices[0]
    log(f"Emulador detectado: {device}", "ok")

    if not APK_OUTPUT.exists():
        log(f"APK no encontrado en {APK_OUTPUT}", "error")
        return False

    # Instalar APK
    log(f"Instalando APK en {device}...", "info")
    out, code = adb_command(["-s", device, "install", "-r", str(APK_OUTPUT)], timeout=120)
    if code == 0 and "Success" in out:
        log("APK instalado correctamente", "ok")
    else:
        log(f"Error instalando APK: {out[-200:]}", "warn")

    # Lanzar app
    log(f"Lanzando {PKG_NAME}/{MAIN_ACTIVITY}...", "info")
    out, code = adb_command(
        ["-s", device, "shell", "am", "start", "-n", f"{PKG_NAME}/{MAIN_ACTIVITY}"], timeout=15
    )
    if code == 0:
        log("App lanzada en el emulador", "ok")
    else:
        log(f"Error lanzando app: {out[-200:]}", "warn")

    return True


# ─── FastAPI Server ───
server_process = None


def start_fastapi_server():
    """Arrancar servidor FastAPI en background."""
    global server_process
    log("🚀 Arrancando servidor FastAPI...", "bold")

    server_cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "core.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(BACKEND_PORT),
        "--reload",
    ]

    try:
        server_process = subprocess.Popen(
            server_cmd,
            cwd=str(Path(__file__).resolve().parent.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Esperar a que el servidor esté listo
        for _ in range(15):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(("127.0.0.1", BACKEND_PORT)) == 0:
                sock.close()
                break
            sock.close()
            time.sleep(0.5)
        else:
            log("Timeout esperando al servidor", "error")
            return False

        log(f"FastAPI corriendo en http://localhost:{BACKEND_PORT}", "ok")
        return True

    except Exception as e:
        log(f"Error iniciando servidor: {e}", "error")
        return False


# ─── Watchdog ───
class EcosystemWatchdog:
    """Watchdog que verifica todos los servicios del ecosistema periódicamente."""

    def __init__(self):
        self._running = threading.Event()
        self._thread = None
        self._results = {}

    def _check_ai_health(self) -> dict:
        """Verificar conectividad con los proveedores de IA."""
        try:
            import asyncio
            from core.proxy_chat_connector import health_check

            result = asyncio.run(health_check())
            return {
                "status": "OK" if result.get("ok") else "DEGRADED",
                "enabled": result.get("enabled_providers", 0),
                "total": result.get("total_providers", 0),
                "message": result.get("message", ""),
            }
        except Exception as e:
            return {"status": "ERROR", "detail": str(e)[:100]}

    def _check_backend(self) -> dict:
        """Verificar que el backend FastAPI responde."""
        try:
            import httpx

            r = httpx.get(f"http://localhost:{BACKEND_PORT}/api/v1/gbrain/health", timeout=5)
            data = r.json() if r.status_code == 200 else {"error": r.text[:100]}
            return {"status": "OK", "port": BACKEND_PORT, "health": data}
        except Exception as e:
            return {"status": "ERROR", "detail": str(e)[:100]}

    def _check_emulator(self) -> dict:
        """Verificar emulador vía ADB."""
        devices = scan_emulator_ports()
        if devices:
            return {"status": "OK", "device": devices[0]}
        return {"status": "NOT_FOUND", "detail": "No emulator detected"}

    def _check_rollercoin(self) -> dict:
        """Verificar estado del bot de Rollercoin."""
        try:
            import httpx

            r = httpx.get(f"http://localhost:{BACKEND_PORT}/api/v1/rollercoin/status", timeout=5)
            data = r.json() if r.status_code == 200 else {}
            return {
                "status": "RUNNING" if data.get("running") else "IDLE",
                "games_played": data.get("games_played", 0),
                "games_won": data.get("games_won", 0),
            }
        except Exception as e:
            return {"status": "ERROR", "detail": str(e)[:100]}

    def _check_ia_providers(self) -> dict:
        """Verificar estado de los proveedores de IA (resumen)."""
        from core.ai_config import get_config

        config = get_config()
        summary = config.get_health_summary()
        chain = config.get_fallback_chain()
        return {
            "providers": summary["providers"],
            "fallback_chain": [p.name for p in chain],
        }

    def run_once(self) -> dict:
        """Ejecutar una verificación completa del ecosistema."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "backend": self._check_backend(),
            "ai_engine": self._check_ai_health(),
            "emulator": self._check_emulator(),
            "rollercoin": self._check_rollercoin(),
            "ai_providers": self._check_ia_providers(),
        }
        self._results = results
        return results

    def _loop(self):
        while self._running.is_set():
            try:
                self.run_once()
                time.sleep(30)  # Check cada 30s
            except:
                pass

    def start(self):
        if not self._running.is_set():
            self._running.set()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            log("Watchdog del ecosistema iniciado (check cada 30s)", "ok")

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=5)


def print_ecosystem_report(results: dict):
    """Imprimir reporte completo del ecosistema en colores."""
    report = f"""
{BOLD}{'═'*60}{RESET}
{BOLD}{GREEN}📊 REPORTE DEL ECOSISTEMA AURA — {results['timestamp']}{RESET}
{BOLD}{'═'*60}{RESET}

{BOLD}1. BACKEND (FastAPI){RESET}
   {GREEN if results['backend']['status'] == 'OK' else RED}Estado: {results['backend']['status']}{RESET}
   Puerto: {results['backend'].get('port', 'N/A')}

{BOLD}2. MOTOR DE IA (Multi-Provider){RESET}
   {GREEN if results['ai_engine']['status'] == 'OK' else YELLOW}Estado: {results['ai_engine']['status']}{RESET}
   Proveedores: {results['ai_engine'].get('enabled', 0)}/{results['ai_engine'].get('total', 0)} habilitados
   Mensaje: {results['ai_engine'].get('message', 'N/A')}

{BOLD}3. CADENA DE FALLBACK IA{RESET}
   {' → '.join(p.get('name', '?') for p in results.get('ai_providers', {}).get('fallback_chain', [])) or '(sin proveedores)'}

{BOLD}4. EMULADOR ANDROID{RESET}
   {GREEN if results['emulator']['status'] == 'OK' else YELLOW}Estado: {results['emulator']['status']}{RESET}
   {f"Dispositivo: {results['emulator']['device']}" if results['emulator']['status'] == 'OK' else results['emulator'].get('detail', '')}

{BOLD}5. ROLLERCOIN BOT{RESET}
   {GREEN if results['rollercoin']['status'] == 'RUNNING' else YELLOW}Estado: {results['rollercoin']['status']}{RESET}
   Juegos: {results['rollercoin'].get('games_played', 0)} | Victorias: {results['rollercoin'].get('games_won', 0)}

{BOLD}6. PROVEEDORES DE IA DETALLADOS:{RESET}
"""
    for p in results.get("ai_providers", {}).get("providers", []):
        icon = "✅" if p.get("enabled") else "❌"
        report += f"   {icon} {p['name']:12s} | modelo: {p['model']}\n"

    report += f"""
{BOLD}{GREEN}{'═'*60}{RESET}
{BOLD}{GREEN}✅ ECOSISTEMA SINCRONIZADO{RESET}
  • App Android → Backend: 10.0.2.2:{BACKEND_PORT}
  • Backend → IA: {results['ai_engine'].get('enabled', 0)}/{results['ai_engine'].get('total', 0)} proveedores
  • Rollercoin: {results['rollercoin']['status']}
  • Emulador: {results['emulator']['status']}
{BOLD}{GREEN}{'═'*60}{RESET}
"""
    print(report)


# ─── Pipeline Principal ───
def main():
    """Pipeline completo: compilar → desplegar → arrancar → monitorear."""
    log("=" * 55, "bold")
    log("🔥 AURA DEPLOY PIPELINE v3 — PC LOCAL + EMULADOR", "bold")
    log("=" * 55, "bold")
    log("Sin cables físicos — ADB vía TCP local", "info")
    log("=" * 55, "bold")

    # FASE 1: Compilar APK
    print()
    log("FASE 1: COMPILACIÓN DEL APK", "bold")
    if not build_apk():
        log("Compilación fallida. Revisa los errores arriba.", "error")
        sys.exit(1)

    # FASE 2: Instalar en Emulador
    print()
    log("FASE 2: DESPLIEGUE EN EMULADOR", "bold")
    install_and_launch_on_emulator()

    # FASE 3: Arrancar Backend
    print()
    log("FASE 3: BACKEND FASTAPI", "bold")
    if not start_fastapi_server():
        log("No se pudo iniciar el backend.", "error")
        sys.exit(1)

    # FASE 4: Iniciar Watchdog
    print()
    log("FASE 4: WATCHDOG DEL ECOSISTEMA", "bold")
    watchdog = EcosystemWatchdog()
    watchdog.start()

    # Pequeña pausa para que el servidor cargue
    time.sleep(3)

    # FASE 5: Reporte inicial
    print()
    log("FASE 5: VERIFICACIÓN DEL ECOSISTEMA", "bold")
    results = watchdog.run_once()
    print_ecosystem_report(results)

    # Mantener el proceso vivo
    log("Pipeline completado. Presiona Ctrl+C para detener todo.", "bold")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        log("Deteniendo servicios...", "warn")
        watchdog.stop()
        if server_process:
            server_process.terminate()
            server_process.wait()
        log("Servicios detenidos. ¡Hasta luego!", "ok")


if __name__ == "__main__":
    main()
