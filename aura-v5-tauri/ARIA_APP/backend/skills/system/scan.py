import socket
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    host = params.get("host", "localhost")
    ports = params.get("ports", [22, 80, 443, 8000])
    open_ports: List[int] = []
    for port in ports:
        try:
            sock = socket.create_connection((host, int(port)), timeout=1)
            sock.close()
            open_ports.append(int(port))
        except Exception:
            pass
    return {"host": host, "open_ports": open_ports, "scanned_ports": len(ports)}
