#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════
# RECON TOOLKIT — Escáner de servicios locales para AME/AURA
# Escanea puertos críticos, detecta la IP local y genera
# network_status.json para que el emulador lo consuma.
# ══════════════════════════════════════════════════════════════

import socket
import json
import os
import time
import platform
from datetime import datetime
from pathlib import Path

# ─── Configuración ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = BASE_DIR / "network_status.json"

# Puertos críticos del ecosistema AURA/AME
CRITICAL_PORTS = {
    5000: "FastAPI (AURA Core)",
    5555: "ADB Emulator",
    8765: "GBrain WebSocket",
    11434: "Ollama Local LLM",
    8080: "Dashboard Web",
    3000: "Node.js Dev Server",
    5001: "API Backup",
    443: "HTTPS External",
}

HF_SERVER = "https://raiden456-slut.hf.space"


def get_local_ip():
    """Obtiene la IP local de la máquina."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def scan_port(host, port, timeout=1.0):
    """Escanea un puerto individual y retorna su estado."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def get_service_name(port):
    """Retorna el nombre del servicio para un puerto dado."""
    return CRITICAL_PORTS.get(port, f"Unknown ({port})")


def scan_all_services(host=None):
    """Escanea todos los puertos críticos y retorna el estado."""
    if host is None:
        host = "127.0.0.1"

    services = {}
    for port, name in CRITICAL_PORTS.items():
        is_active = scan_port(host, port, timeout=1.5)
        services[str(port)] = {
            "name": name,
            "port": port,
            "active": is_active,
            "status": "ONLINE" if is_active else "OFFLINE",
        }
    return services


def check_hf_server():
    """Verifica si el servidor Hugging Face está accesible."""
    try:
        import urllib.request

        req = urllib.request.Request(f"{HF_SERVER}/health", method="GET")
        req.add_header("User-Agent", "AURA-Recon/1.0")
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status == 200
    except Exception:
        return False


def generate_network_status():
    """Genera el archivo network_status.json con el estado completo."""
    local_ip = get_local_ip()
    services = scan_all_services("127.0.0.1")
    hf_online = check_hf_server()

    # También escaneamos desde la perspectiva del emulador (10.0.2.2)
    emulator_services = scan_all_services("10.0.2.2")

    status = {
        "timestamp": datetime.now().isoformat(),
        "host_info": {
            "local_ip": local_ip,
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "emulator_bridge": "10.0.2.2",
        },
        "huggingface_server": {
            "url": HF_SERVER,
            "online": hf_online,
            "model": "qwen2.5-coder-3b-abliterated",
        },
        "services_local": services,
        "services_from_emulator": emulator_services,
        "summary": {
            "total_services": len(services),
            "active_local": sum(1 for s in services.values() if s["active"]),
            "active_from_emulator": sum(1 for s in emulator_services.values() if s["active"]),
            "hf_online": hf_online,
        },
    }

    # Guardar archivo JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

    return status


def print_report(status):
    """Imprime un reporte legible en consola."""
    print("=" * 60)
    print("🔍 AURA RECON TOOLKIT — Network Status Report")
    print("=" * 60)
    print(f"⏰ Timestamp: {status['timestamp']}")
    print(f"🖥️  IP Local:  {status['host_info']['local_ip']}")
    print(f"📡 Hostname:  {status['host_info']['hostname']}")
    print()

    print("🌐 Hugging Face Server:")
    hf = status["huggingface_server"]
    icon = "✅" if hf["online"] else "❌"
    print(f"   {icon} {hf['url']} → {'ONLINE' if hf['online'] else 'OFFLINE'}")
    print(f"   🤖 Modelo: {hf['model']}")
    print()

    print("🔌 Servicios Locales (127.0.0.1):")
    for port_str, info in status["services_local"].items():
        icon = "🟢" if info["active"] else "🔴"
        print(f"   {icon} :{port_str} — {info['name']} → {info['status']}")
    print()

    print("📱 Servicios desde Emulador (10.0.2.2):")
    for port_str, info in status["services_from_emulator"].items():
        icon = "🟢" if info["active"] else "🔴"
        print(f"   {icon} :{port_str} — {info['name']} → {info['status']}")
    print()

    s = status["summary"]
    print(f"📊 Resumen: {s['active_local']}/{s['total_services']} servicios activos localmente")
    print(f"📱 Emulador ve: {s['active_from_emulator']}/{s['total_services']} servicios")
    print("=" * 60)


if __name__ == "__main__":
    status = generate_network_status()
    print_report(status)
    print(f"\n💾 Estado guardado en: {OUTPUT_FILE}")
