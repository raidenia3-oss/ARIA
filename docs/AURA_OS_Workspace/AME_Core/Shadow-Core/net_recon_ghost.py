"""
net_recon_ghost.py - Módulo de escaneo de red furtivo (simulado)
Escaneo TCP SYN Stealth + descubrimiento de hosts ARP
Integrado como módulo del Shadow-Core
"""

import json
import time
import random
from typing import Dict, List, Optional

# --- CONFIGURACIÓN ---
TARGET_SUBNET = "192.168.1.0/24"
STEALTH_PORTS = [80, 443, 8080, 554]
TIMEOUT = 2
RETRY = 1

# --- DATOS SIMULADOS ---
SIMULATED_HOSTS = [
    {"ip": "192.168.1.1", "mac": "00:11:22:33:44:55", "services": {"80": "HTTP", "443": "HTTPS"}},
    {"ip": "192.168.1.2", "mac": "aa:bb:cc:dd:ee:ff", "services": {"8080": "HTTP"}},
    {"ip": "192.168.1.3", "mac": "11:22:33:44:55:66", "services": {"554": "RTSP"}},
]

def get_mac(ip: str) -> Optional[str]:
    """Simula la resolución de MAC de una IP."""
    for host in SIMULATED_HOSTS:
        if host["ip"] == ip:
            return host["mac"]
    return None

def syn_stealth_scan(target_ip: str, ports: List[int]) -> Dict[int, str]:
    """Simula un escaneo TCP SYN Stealth en los puertos especificados."""
    open_ports = {}
    for port in ports:
        # Simular resultados aleatorios
        if random.random() < 0.7:  # 70% de probabilidad de que el puerto esté abierto
            open_ports[port] = "open"
        else:
            open_ports[port] = "closed"
    return open_ports

def discover_hosts(subnet: str) -> List[str]:
    """Simula el descubrimiento de hosts activos en la subred."""
    return [host["ip"] for host in SIMULATED_HOSTS]

def map_services(ip: str, open_ports: List[int]) -> Dict[str, str]:
    """Simula la identificación de servicios en los puertos abiertos."""
    service_map = {}
    for port in open_ports:
        if port in (80, 8080):
            service_map[str(port)] = "HTTP"
        elif port == 443:
            service_map[str(port)] = "HTTPS"
        elif port == 554:
            service_map[str(port)] = "RTSP"
        else:
            service_map[str(port)] = "unknown"
    return service_map

def run_recon(subnet: Optional[str] = None, ports: Optional[List[int]] = None) -> Dict:
    """Función principal orquestada. Retorna dict listo para JSON serializable."""
    target = subnet or TARGET_SUBNET
    target_ports = ports or STEALTH_PORTS

    print(f"[GHOST_RECON] Escaneo furtivo simulado en: {target}")

    recon_results = {
        "scan_timestamp": time.time(),
        "subnet": target,
        "hosts": []
    }

    active_hosts = discover_hosts(target)
    print(f"[GHOST_RECON] {len(active_hosts)} hosts activos simulados.")

    for ip in active_hosts:
        host_info = {"ip": ip, "mac": get_mac(ip)}
        port_results = syn_stealth_scan(ip, target_ports)
        open_ports_list = [p for p, s in port_results.items() if s == "open"]

        if open_ports_list:
            host_info["services"] = map_services(ip, open_ports_list)
            host_info["open_ports"] = open_ports_list
            recon_results["hosts"].append(host_info)
            print(f"[GHOST_RECON] Host {ip}: puertos abiertos {open_ports_list}")

    return recon_results