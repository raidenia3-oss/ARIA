"""AURA Mobile Client — Utilidades de red local y descubrimiento UDP.

Escanea la red WiFi local mediante broadcast UDP para detectar
automaticamente el servidor AURA en el puerto 8000.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
from typing import Callable, List, Optional, Tuple

DISCOVERY_PORT = 8000
DISCOVERY_MSG = b"AURA_DISCOVER"
DISCOVERY_RESP = b"AURA_HERE"
DISCOVERY_TIMEOUT = 3.0
MAX_DISCOVERY_RETRIES = 3


def _get_local_ip() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return None


def _get_subnet_prefix(ip: str) -> Optional[str]:
    try:
        iface = ipaddress.ip_interface(f"{ip}/24")
        return str(iface.network)
    except Exception:
        return None


def discover_server(
    port: int = DISCOVERY_PORT,
    timeout: float = DISCOVERY_TIMEOUT,
    retries: int = MAX_DISCOVERY_RETRIES,
    on_found: Optional[Callable[[str], None]] = None,
) -> List[str]:
    found: List[str] = []

    def _scan():
        local_ip = _get_local_ip()
        if not local_ip:
            return
        prefix = _get_subnet_prefix(local_ip)
        if not prefix:
            return
        network = ipaddress.ip_network(prefix, strict=False)

        for attempt in range(retries):
            for host in network.hosts():
                ip_str = str(host)
                if ip_str == local_ip:
                    continue
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(timeout / max(retries, 1))
                        s.sendto(DISCOVERY_MSG, (ip_str, port))
                        data, _ = s.recvfrom(1024)
                        if data == DISCOVERY_RESP:
                            if ip_str not in found:
                                found.append(ip_str)
                                if on_found:
                                    on_found(ip_str)
                except Exception:
                    continue

    threading.Thread(target=_scan, daemon=True).start()
    return found


def broadcast_presence(port: int = DISCOVERY_PORT, bind_port: int = 0) -> None:
    def _listen():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("", port))
                except OSError:
                    return
                s.settimeout(1.0)
                while True:
                    try:
                        data, addr = s.recvfrom(1024)
                        if data == DISCOVERY_MSG:
                            s.sendto(DISCOVERY_RESP, addr)
                    except socket.timeout:
                        continue
                    except Exception:
                        break
        except Exception:
            pass
    threading.Thread(target=_listen, daemon=True).start()


def measure_latency(base_url: str, timeout: float = 2.0) -> Optional[float]:
    import time
    try:
        start = time.perf_counter()
        import requests
        requests.get(f"{base_url}/api/health", timeout=timeout)
        return time.perf_counter() - start
    except Exception:
        return None
