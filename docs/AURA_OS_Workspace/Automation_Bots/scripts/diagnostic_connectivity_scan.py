#!/usr/bin/env python3
"""
Escáner de diagnóstico local para el ecosistema AURA.
Valida si el servidor actual escucha en el puerto 8000,
obtiene la IP activa de la interfaz inalámbrica y
exporta un JSON de prueba para un "Nodo de Conectividad".
"""

import json
import platform
import socket
import subprocess
import sys
from datetime import datetime


def check_port_8000(host="127.0.0.1", timeout=1.0):
    try:
        with socket.create_connection((host, 8000), timeout=timeout):
            return True
    except Exception:
        return False


def parse_windows_wlan_interfaces(output):
    iface_name = None
    ip_address = None
    for line in output.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized.lower().startswith("nombre de la interfaz") or normalized.lower().startswith("name"):
            iface_name = normalized.split(":", 1)[-1].strip()
        elif normalized.lower().startswith("dirección ipv4") or normalized.lower().startswith("ipv4 address"):
            ip_address = normalized.split(":", 1)[-1].strip().split("(")[0].strip()
            break
    return iface_name, ip_address


def get_wireless_ip_windows():
    try:
        output = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )
        return parse_windows_wlan_interfaces(output)
    except Exception:
        return None, None


def get_default_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def detect_wireless_ip():
    system = platform.system().lower()
    if system == "windows":
        iface, ip = get_wireless_ip_windows()
        if ip:
            return iface or "wireless", ip
    return None, None


def make_connectivity_node_json(port_ok, iface, ip):
    node = {
        "node_type": "Nodo de Conectividad",
        "node_id": "connectivity-node-001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": {
            "port_8000_listening": port_ok,
            "wireless_interface": iface,
            "wireless_ip": ip,
            "local_ip_fallback": get_default_ip(),
        },
        "connectivity": {
            "name": "AURA Nodo de Conectividad",
            "description": "Nodo de diagnóstico de red para el motor dinámico",
            "endpoints": [
                {
                    "protocol": "http",
                    "host": ip or get_default_ip(),
                    "port": 8000,
                }
            ],
            "properties": {
                "dynamic_engine_compatible": True,
                "validation_mode": "diagnostic-scan",
            },
        },
    }
    return node


def main():
    port_ok = check_port_8000()
    iface, wireless_ip = detect_wireless_ip()

    result = make_connectivity_node_json(port_ok, iface, wireless_ip)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if port_ok:
        print("\n✅ Puerto 8000: escuchando")
    else:
        print("\n⚠️ Puerto 8000: no se detectó ningún servicio escuchando en localhost:8000")

    if wireless_ip:
        print(f"✅ IP inalámbrica activa ({iface}): {wireless_ip}")
    else:
        print("⚠️ No se pudo detectar una IP inalámbrica activa con el método de diagnóstico local")

    return 0


if __name__ == "__main__":
    sys.exit(main())
