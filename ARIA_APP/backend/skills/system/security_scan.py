import os
import socket
from typing import Any, Dict, List

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 3306, 3389, 5432, 6379, 8080, 27017]


def scan_ports(host: str = "127.0.0.1", ports: List[int] = COMMON_PORTS, timeout: float = 0.2) -> List[Dict[str, Any]]:
    open_ports = []
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                open_ports.append({"port": port, "state": "open"})
        except Exception:
            pass
    return open_ports


def suspicious_files(root: str = ".") -> List[str]:
    found = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            low = name.lower()
            if low.endswith((".env", ".pem", ".key", "id_rsa")) or "password" in low or "secret" in low:
                found.append(os.path.join(dirpath, name))
        if len(found) > 50:
            return found
    return found


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    host = str(params.get("host", "127.0.0.1"))
    root = str(params.get("root", "."))
    return {
        "status": "ok",
        "host": host,
        "open_ports": scan_ports(host),
        "suspicious_files": suspicious_files(root),
        "python_version": __import__("sys").version.split()[0],
    }
