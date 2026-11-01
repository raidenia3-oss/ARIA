from __future__ import annotations

import re
import socket
from typing import Any, Dict


def _normalize_mac(mac: str) -> bytes:
    mac = mac.strip().replace(":", "").replace("-", "").replace(".", "")
    if not re.fullmatch(r"[0-9a-fA-F]{12}", mac):
        raise ValueError(f"MAC invalida: {mac!r}")
    return bytes.fromhex(mac)


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255",
                      port: int = 9, repeats: int = 3) -> Dict[str, Any]:
    mac_bytes = _normalize_mac(mac)
    payload = b"\xff" * 6 + mac_bytes * 16  # 102 bytes
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        for _ in range(repeats):
            sock.sendto(payload, (broadcast, port))
        return {"ok": True, "mac": mac, "broadcast": broadcast,
                "port": port, "payload_bytes": len(payload), "repeats": repeats}
    finally:
        sock.close()


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    mac = params.get("mac")
    if not mac:
        return {"ok": False, "error": "parametro 'mac' requerido (AA:BB:CC:DD:EE:FF)"}
    try:
        return send_magic_packet(
            mac=mac,
            broadcast=params.get("broadcast", "255.255.255.255"),
            port=int(params.get("port", 9)),
            repeats=int(params.get("repeats", 3)),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
