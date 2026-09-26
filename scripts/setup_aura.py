"""
AURA Setup Wizard — Configuración Inicial
==========================================
Detecta el entorno, las apps instaladas, y genera el archivo .env.local
listo para que solo tengas que pegar tus API keys.

Uso:
  python scripts/setup_aura.py                    # Modo interactivo
  python scripts/setup_aura.py --check            # Solo verificar estado
  python scripts/setup_aura.py --generate-env     # Generar .env.local con defaults
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / "ame_backend" / ".env.local"


def check_python() -> Dict[str, Any]:
    version = sys.version_info
    return {
        "name": "Python",
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "ok": version.major >= 3 and version.minor >= 9,
    }


def check_jan() -> Dict[str, Any]:
    jan_paths = [
        os.environ.get("LOCALAPPDATA", "") + "\\Programs\\jan\\Jan.exe",
        os.environ.get("LOCALAPPDATA", "") + "\\Programs\\Jan\\Jan.exe",
    ]
    for p in jan_paths:
        if os.path.exists(p):
            running = False
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq Jan.exe"],
                    capture_output=True, text=True, timeout=5
                )
                running = "Jan.exe" in result.stdout
            except Exception:
                pass
            return {
                "name": "Jan",
                "installed": True,
                "running": running,
                "path": p,
                "api_url": "http://localhost:1337/v1",
            }
    return {"name": "Jan", "installed": False, "running": False}


def check_fastapi_uvicorn() -> Dict[str, Any]:
    fastapi_ok = False
    uvicorn_ok = False
    try:
        import fastapi
        fastapi_ok = True
    except ImportError:
        pass
    try:
        import uvicorn
        uvicorn_ok = True
    except ImportError:
        pass
    return {
        "name": "FastAPI + Uvicorn",
        "fastapi": fastapi_ok,
        "uvicorn": uvicorn_ok,
        "ok": fastapi_ok and uvicorn_ok,
    }


def check_adb() -> Dict[str, Any]:
    adb = shutil.which("adb")
    if adb:
        try:
            result = subprocess.run([adb, "version"], capture_output=True, text=True, timeout=5)
            version = result.stdout.split("\n")[0] if result.returncode == 0 else "unknown"
            devices = []
            try:
                result = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=5)
                for line in result.stdout.strip().split("\n")[1:]:
                    if line.strip() and not line.startswith("List"):
                        parts = line.split()
                        if len(parts) >= 2:
                            devices.append({"id": parts[0], "status": parts[1]})
            except Exception:
                pass
            return {
                "name": "ADB (Android)",
                "available": True,
                "path": adb,
                "version": version,
                "devices": devices,
                "device_count": len(devices),
            }
        except Exception:
            pass
    return {"name": "ADB (Android)", "available": False}


def check_obs() -> Dict[str, Any]:
    paths = [
        "C:\\Program Files\\OBS Studio\\bin\\64bit\\obs64.exe",
        "C:\\Program Files (x86)\\OBS Studio\\bin\\64bit\\obs64.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return {"name": "OBS Studio", "installed": True, "path": p}
    return {"name": "OBS Studio", "installed": False}


def check_godot() -> Dict[str, Any]:
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    lnk = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Godot_v4.lnk"
    )
    if os.path.exists(lnk):
        shortcut = shell.CreateShortCut(lnk)
        target = shortcut.Targetpath
        if target and os.path.exists(target):
            return {"name": "Godot", "installed": True, "path": target}
    paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Godot", "godot.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Godot", "godot.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return {"name": "Godot", "installed": True, "path": p}
    portable = os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Godot_v4-stable_win64.exe")
    if os.path.exists(portable):
        return {"name": "Godot", "installed": True, "path": portable, "portable": True}
    return {"name": "Godot", "installed": False}


def check_obsidian() -> Dict[str, Any]:
    paths = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Obsidian", "Obsidian.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Obsidian", "Obsidian.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return {"name": "Obsidian", "installed": True, "path": p}
    return {"name": "Obsidian", "installed": False}


def check_android_studio() -> Dict[str, Any]:
    paths = [
        "C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe",
        "C:\\Program Files (x86)\\Android\\Android Studio\\bin\\studio64.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return {"name": "Android Studio", "installed": True, "path": p}
    return {"name": "Android Studio", "installed": False}


def check_unity_hub() -> Dict[str, Any]:
    paths = [
        "C:\\Program Files\\Unity Hub\\Unity Hub.exe",
        "C:\\Program Files (x86)\\Unity Hub\\Unity Hub.exe",
    ]
    for p in paths:
        if os.path.exists(p):
            return {"name": "Unity Hub", "installed": True, "path": p}
    return {"name": "Unity Hub", "installed": False}


def check_python_apps() -> Dict[str, Any]:
    python_exe = shutil.which("python") or shutil.which("python3")
    pip = shutil.which("pip") or shutil.which("pip3")
    packages = {}
    if pip:
        for pkg in ["fastapi", "uvicorn", "requests", "pywin32"]:
            try:
                result = subprocess.run(
                    [pip, "show", pkg],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.startswith("Version:"):
                            packages[pkg] = line.split(":", 1)[1].strip()
                            break
            except Exception:
                pass
    return {
        "name": "Python + Packages",
        "python": python_exe,
        "pip": pip,
        "packages": packages,
        "ok": bool(python_exe),
    }


def run_full_check() -> Dict[str, Any]:
    checks = {
        "python": check_python(),
        "jan": check_jan(),
        "fastapi_uvicorn": check_fastapi_uvicorn(),
        "adb_android": check_adb(),
        "obs": check_obs(),
        "godot": check_godot(),
        "obsidian": check_obsidian(),
        "android_studio": check_android_studio(),
        "unity_hub": check_unity_hub(),
        "python_apps": check_python_apps(),
    }

    all_ok = all(
        v.get("ok", v.get("installed", v.get("available", False)))
        for v in checks.values()
        if v.get("name") != "OBS Studio"
    )

    return {
        "checks": checks,
        "all_ok": all_ok,
        "timestamp": __import__("time").time(),
    }


def generate_env_template() -> str:
    return """# ─────────────────────────────────────────────────────────────
# AURA .env.local — Pegá tus API keys en los campos vacíos abajo
# Conseguí keys gratuitas en:
#   Groq:        https://console.groq.com/keys
#   DeepSeek:    https://platform.deepseek.com/api_keys
#   OpenRouter:  https://openrouter.ai/keys
#   Nvidia NIM:  https://build.nvidia.com
#   Mistral:     https://console.mistral.ai
#   Gemini:      https://aistudio.google.com/app/apikey
# ─────────────────────────────────────────────────────────────

DATABASE_URL=sqlite:///./aura.db
JWT_SECRET=dev-secret-aura-localhost-auto
BRIDGE_SECRET=dev-secret-bridge-localhost-auto
FRONTEND_URL=http://localhost:3000

HF_TOKEN=hf_YOUR_TOKEN_HERE
HF_MODEL=google/gemma-2-9b-it
HF_TIMEOUT=60

# Gemini (multimodal, recomendado)
GEMINI_API_KEY=pegá_tu_key_aquí
GEMINI_MODEL=gemini-2.0-flash-exp
GEMINI_TIMEOUT=30

# Groq (muy rápido, FREE tier generoso)
GROQ_API_KEY=gsk_pegá_tu_key_aquí
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT=30

# OpenRouter (cientos de modelos, FREE tier)
OPENROUTER_API_KEY=sk-or-v1-pegá_tu_key_aquí
OPENROUTER_MODEL=meta-llama/llama-3-8b-instruct:free
OPENROUTER_TIMEOUT=30

# DeepSeek (DeepSeek-V3, FREE)
DEEPSEEK_API_KEY=sk-pegá_tu_key_aquí
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_TIMEOUT=30

# Nvidia NIM (Llama, FREE tier)
NVIDIA_API_KEY=nvapi-pegá_tu_key_aquí
NVIDIA_MODEL=meta/llama-3-70b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_TIMEOUT=30

# Mistral (FREE tier)
MISTRAL_API_KEY=pegá_tu_key_aquí
MISTRAL_MODEL=mistral-small-latest
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_TIMEOUT=30

# Jan (modelo local — no necesita key)
JAN_BASE_URL=http://localhost:1337/v1
JAN_MODEL=qwen2.5-0.5b-instruct
JAN_TIMEOUT=120

# Knowledge Distillation
KD_TOP_K_EXAMPLES=3
KD_MIN_SIMILARITY=0.30
KD_MAX_HISTORY=5000

# Router
AURA_ROUTER_STRATEGY=auto
AURA_ROUTER_JAN_FIRST=true
AURA_ROUTER_CLOUD_FALLBACK=true
AURA_AUTO_CLASSIFY=true
AURA_COMPLEX_PROVIDERS=gemini,groq,nvidia,deepseek,mistral
AURA_MEDIUM_PROVIDERS=groq,deepseek,mistral,openrouter
AURA_SIMPLE_PROVIDERS=jan

# Learning Engine
LEARNING_ENABLED=true
LEARNING_EVAL_INTERVAL=300
LEARNING_MAX_MODIFICATIONS=10
LEARNING_BACKUP_BEFORE_MOD=true
LEARNING_SAFE_MODE=false
"""


def generate_setup_summary() -> str:
    check = run_full_check()
    lines = []
    lines.append("=" * 60)
    lines.append("  AURA SETUP — ESTADO DEL SISTEMA")
    lines.append("=" * 60)
    lines.append("")

    for key, data in check["checks"].items():
        name = data.get("name", key)
        status = "OK" if data.get("ok", data.get("installed", data.get("available", False))) else "FALTA"
        lines.append(f"  [{status}] {name}")
        if not data.get("ok", data.get("installed", data.get("available", False))):
            if key == "jan":
                lines.append("         -> Instalalo desde https://jan.ai/")
            elif key == "fastapi_uvicorn":
                lines.append("         -> pip install fastapi uvicorn")
            elif key == "adb_android":
                lines.append("         -> Instala Android SDK Platform Tools")
            elif key == "godot":
                lines.append("         -> Instala Godot 4 desde https://godotengine.org/")
            elif key == "obsidian":
                lines.append("         -> Instala Obsidian desde https://obsidian.md/")
            elif key == "python_apps":
                lines.append("         -> pip install -r requirements.txt")

    lines.append("")
    lines.append("-" * 60)
    if check["all_ok"]:
        lines.append("  TODO LISTO -- Ejecuta scripts/start_aura_local.bat")
    else:
        lines.append("  FALTAN COSAS -- Revisa los items marcados arriba")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    args = sys.argv[1:]

    if "--check" in args:
        print(generate_setup_summary())
        return

    if "--generate-env" in args:
        if ENV_FILE.exists():
            print(f"[WARN] {ENV_FILE} ya existe. Sobrescribir? (s/n): ", end="")
            resp = input().strip().lower()
            if resp != "s":
                print("Cancelado.")
                return
        ENV_FILE.write_text(generate_env_template(), encoding="utf-8")
        print(f"[OK] Generado: {ENV_FILE}")
        print("Ahora editá el archivo y pegá tus API keys.")
        return

    # Modo interactivo
    print(generate_setup_summary())
    print()
    print("Opciones:")
    print("  1. Generar .env.local con template (para pegar API keys)")
    print("  2. Verificar conexión con Jan")
    print("  3. Verificar dispositivos conectados")
    print("  4. Ver todo el estado detallado")
    print("  0. Salir")
    print()

    try:
        choice = input("Elegí una opción: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        if ENV_FILE.exists():
            print(f"[WARN] {ENV_FILE} ya existe.")
            overwrite = input("Sobrescribir? (s/n): ").strip().lower()
            if overwrite != "s":
                print("Cancelado.")
                return
        ENV_FILE.write_text(generate_env_template(), encoding="utf-8")
        print(f"[OK] .env.local generado en: {ENV_FILE}")
        print("Editá el archivo y pegá tus API keys.")

    elif choice == "2":
        jan = check_jan()
        if jan["installed"]:
            print(f"[OK] Jan instalado: {jan['path']}")
            print(f"     API: {jan['api_url']}")
            print(f"     Corriendo: {'Sí' if jan['running'] else 'No'}")
            if jan["running"]:
                try:
                    import requests
                    resp = requests.get("http://localhost:1337/v1/models", timeout=3)
                    if resp.status_code == 200:
                        models = [m.get("id", "") for m in resp.json().get("data", [])]
                        print(f"     Modelos: {', '.join(models)}")
                except Exception as exc:
                    print(f"     [WARN] No se pudo consultar API: {exc}")
        else:
            print("[FALTA] Jan no está instalado.")
            print("        Instalalo desde https://jan.ai/")

    elif choice == "3":
        print("\n── Android (ADB) ──")
        adb = check_adb()
        if adb["available"]:
            print(f"[OK] ADB: {adb['path']}")
            print(f"     Versión: {adb['version']}")
            if adb["devices"]:
                for dev in adb["devices"]:
                    print(f"     Dispositivo: {dev['id']} ({dev['status']})")
            else:
                print("     No hay dispositivos conectados")
        else:
            print("[FALTA] ADB no disponible")

        print("\n── USB ──")
        usb = mgr.list_usb_devices()
        if usb:
            for dev in usb[:5]:
                print(f"     {dev.get('name', 'Unknown')} ({dev.get('status', '')})")
        else:
            print("     No hay dispositivos USB detectados")

    elif choice == "4":
        check = run_full_check()
        print(json.dumps(check, indent=2, ensure_ascii=False))

    elif choice == "0":
        return

    else:
        print("Opción inválida.")


if __name__ == "__main__":
    main()
