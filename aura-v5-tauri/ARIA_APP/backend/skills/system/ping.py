import socket
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    host = params.get("host", "8.8.8.8")
    port = params.get("port", 80)
    timeout = float(params.get("timeout", 2))
    try:
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        return {"host": host, "port": port, "status": "reachable"}
    except Exception as e:
        return {"host": host, "port": port, "status": "unreachable", "error": str(e)}
