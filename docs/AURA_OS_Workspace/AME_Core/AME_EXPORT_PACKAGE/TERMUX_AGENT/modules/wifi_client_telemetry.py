#!/usr/bin/env python3
"""
wifi_client_telemetry.py - Cliente de telemetría WiFi para AURA en Termux.
Escanea la red local, reporta estado del nodo y se conecta al servidor de
telemetría de la PC central vía WebSocket.

Optimizado para ejecutarse directamente en Termux sin dependencias nativas.
Solo requiere: pip install requests websockets
"""
import json
import socket
import time
import os
import platform
import subprocess
import asyncio
from datetime import datetime
from typing import Optional, Dict, List

try:
    import requests
except ImportError:
    requests = None

try:
    import websockets
except ImportError:
    websockets = None

# ─── Configuración por defecto ───────────────────────────────────────────────
AURA_BASE = "/data/data/com.termux/files/home"
CONFIG_PATH = os.path.join(AURA_BASE, "AME-termux", "config.json")
DEFAULT_CONFIG = {
    "aura_pc_url": "ws://192.168.1.100:8765",
    "telemetry_port": 9900,
    "scan_interval_sec": 30,
    "node_id": "ame-mobile-01",
    "node_role": "osint-recon"
}


def load_config() -> Dict:
    """Carga configuración desde config.json o usa defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                user_cfg = json.load(f)
                cfg = {**DEFAULT_CONFIG, **user_cfg}
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def get_local_ip() -> str:
    """Obtiene la IP local del dispositivo."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_ssid_termux() -> Optional[str]:
    """Obtiene el SSID de la red WiFi actual (solo Android/Termux)."""
    try:
        result = subprocess.run(
            ["termux-wifi-connectioninfo"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("ssid", None)
    except Exception:
        pass
    return None


def scan_local_network(cidr: str = None) -> List[Dict]:
    """Escanea la red local buscando hosts activos (método ARP/ping básico)."""
    hosts = []
    local_ip = get_local_ip()
    base = ".".join(local_ip.split(".")[:3])

    # Escaneo rápido de 20 IPs más probables
    for i in [1, 2, 100, 101, 150, 200, 254, 50, 75, 125]:
        ip = f"{base}.{i}"
        if ip == local_ip:
            continue
        try:
            param = "-n" if platform.system().lower() == "windows" else "-c"
            timeout_param = "-w" if platform.system().lower() != "windows" else "-n"
            result = subprocess.run(
                ["ping", param, "1", timeout_param, "1", ip],
                capture_output=True, timeout=2
            )
            if result.returncode == 0:
                # Intentar resolver hostname
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    hostname = "unknown"
                hosts.append({"ip": ip, "hostname": hostname, "status": "up"})
        except Exception:
            continue
    return hosts


def get_node_status() -> Dict:
    """Recopila estado completo del nodo móvil."""
    config = load_config()
    local_ip = get_local_ip()
    ssid = get_ssid_termux()

    # Información del sistema
    uptime = "unknown"
    try:
        with open("/proc/uptime", "r") as f:
            uptime_sec = float(f.read().split()[0])
            hours = int(uptime_sec // 3600)
            minutes = int((uptime_sec % 3600) // 60)
            uptime = f"{hours}h {minutes}m"
    except Exception:
        pass

    # Espacio en disco
    disk_usage = "unknown"
    try:
        result = subprocess.run(
            ["df", "-h", "/data/data/com.termux"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    disk_usage = f"{parts[2]}/{parts[1]} ({parts[4]})"
    except Exception:
        pass

    # Memoria
    mem_info = "unknown"
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    mem_info = f"{kb // 1024}MB available"
                    break
    except Exception:
        pass

    # Procesos de AURA activos
    aura_procs = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python.*ame"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            aura_procs = result.stdout.strip().split("\n")
    except Exception:
        pass

    return {
        "node_id": config["node_id"],
        "node_role": config["node_role"],
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "network": {
            "local_ip": local_ip,
            "ssid": ssid,
            "gateway": f"{'.'.join(local_ip.split('.')[:3])}.1"
        },
        "system": {
            "uptime": uptime,
            "disk_usage": disk_usage,
            "memory": mem_info,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "termux": os.path.exists("/data/data/com.termux"),
            "aura_processes": len([p for p in aura_procs if p])
        },
        "modules_loaded": [
            "osint_username",
            "osint_reputation",
            "wifi_client_telemetry"
        ]
    }


async def send_telemetry_pc(config: Dict, status: Dict):
    """Envía telemetría al servidor PC vía WebSocket."""
    if not websockets:
        print("[!] websockets no instalado. pip install websockets")
        return False

    uri = config.get("aura_pc_url", "ws://192.168.1.100:8765")
    try:
        async with websockets.connect(uri, timeout=10) as ws:
            payload = {
                "type": "telemetry",
                "source": config["node_id"],
                "data": status
            }
            await ws.send(json.dumps(payload))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"[+] Telemetría enviada. Respuesta: {response}")
            return True
    except Exception as e:
        print(f"[!] Error enviando telemetría a PC: {e}")
        return False


async def start_telemetry_loop(config: Dict):
    """Bucle principal de telemetría periódica."""
    interval = config.get("scan_interval_sec", 30)
    print(f"[*] Iniciando telemetría cada {interval}s...")
    print(f"[*] Nodo: {config['node_id']} | Rol: {config['node_role']}")
    print(f"[*] PC Central: {config.get('aura_pc_url', 'no configurada')}")

    while True:
        try:
            status = get_node_status()
            print(f"\n[{status['timestamp']}] Estado del nodo:")
            print(f"  IP: {status['network']['local_ip']}")
            print(f"  SSID: {status['network']['ssid'] or 'N/A'}")
            print(f"  Uptime: {status['system']['uptime']}")
            print(f"  Procesos AURA: {status['system']['aura_processes']}")

            # Enviar a PC central
            await send_telemetry_pc(config, status)

            # Guardar snapshot local
            snapshot_path = os.path.join(AURA_BASE, "AME-termux", "logs", "telemetry_snapshot.json")
            os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
            with open(snapshot_path, "w") as f:
                json.dump(status, f, indent=2)

        except Exception as e:
            print(f"[!] Error en ciclo de telemetría: {e}")

        await asyncio.sleep(interval)


def start_standalone():
    """Modo standalone: imprime estado una vez y sale."""
    config = load_config()
    status = get_node_status()
    print(json.dumps(status, indent=2))
    return status


def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        config = load_config()
        asyncio.run(start_telemetry_loop(config))
    elif len(sys.argv) > 1 and sys.argv[1] == "--scan":
        hosts = scan_local_network()
        print(json.dumps(hosts, indent=2))
    else:
        start_standalone()


if __name__ == "__main__":
    main()