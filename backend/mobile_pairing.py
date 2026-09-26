"""Local-first PC ⇄ Mobile pairing (AURA HOST ⇄ AME CLIENT).

Genera perfiles de conexión LAN con un código de emparejamiento efímero de
un solo uso ligado a un token HMAC del proceso. Al canjearlo, el cliente
móvil queda registrado y aprobado en `DeviceAuthManager` (sin modificarlo)
y recibe la URL base persistente del host.

Flujo:
1. HOST: GET /api/mobile/pairing/profile → {host_ip, port, code, token, qr_payload}
2. MOBILE: POST /api/mobile/pairing/handshake {code, token, device_id, device_name}
           → {status:"paired", device_token, backend_url}
3. Health-check de latencia: GET /api/mobile/pairing/ping

El código expira (PAIRING_TTL_SECONDS) y es de un solo uso. El token del
perfil es HMAC-SHA256(proceso, code) → no falsificable desde la LAN.
Sin secretos en disco ni en texto plano en logs.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/mobile/pairing", tags=["mobile_pairing"])

PAIRING_TTL_SECONDS = 600  # 10 minutos
_CODE_SECRET = secrets.token_bytes(32)  # solo en memoria del proceso
_pending_codes: Dict[str, Dict[str, Any]] = {}
_paired_codes: set = set()
_lock = threading.Lock()


def get_local_ip(preferred_port: int = 0) -> str:
    """IP local de salida (LAN). Truco UDP: no envía paquetes a Internet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.255.255", 1))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _is_lan_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def list_local_ips() -> List[str]:
    """IPs privadas de todas las interfaces LAN disponibles."""
    try:
        hostname_ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        hostname_ips = []
    lan = [ip for ip in hostname_ips if _is_lan_ip(ip) and not ip.endswith(".1")]
    primary = get_local_ip()
    if primary not in lan and _is_lan_ip(primary):
        lan.insert(0, primary)
    return lan or [primary]


def _pairing_token(code: str, expires_at: float) -> str:
    """Token HMAC-SHA256 ligado al código y su expiración (no falsificable)."""
    msg = f"{code}:{expires_at}".encode()
    return hmac.new(_CODE_SECRET, msg, hashlib.sha256).hexdigest()


def _code_from_qr_payload(qr_payload: str) -> Optional[Dict[str, Any]]:
    """Parsea el payload JSON embebido en el QR del host."""
    try:
        data = json.loads(qr_payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("code") or not data.get("token"):
        return None
    return data


def create_pairing_profile(backend_port: int = 8000) -> Dict[str, Any]:
    """Genera un código efímero + token firmado + payload para QR."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = time.time() + PAIRING_TTL_SECONDS
    token = _pairing_token(code, expires_at)
    host_ip = get_local_ip()
    with _lock:
        # Un solo código activo a la vez mantiene el modelo simple y seguro.
        _pending_codes.clear()
        _pending_codes[code] = {"expires_at": expires_at, "token": token}
    qr_payload = json.dumps(
        {
            "kind": "aura_pairing",
            "v": 1,
            "host": host_ip,
            "port": backend_port,
            "code": code,
            "token": token,
            "exp": int(expires_at),
        },
        separators=(",", ":"),
    )
    return {
        "host_ip": host_ip,
        "host_ips": list_local_ips(),
        "port": backend_port,
        "backend_url": f"http://{host_ip}:{backend_port}",
        "code": code,
        "token": token,
        "expires_at": int(expires_at),
        "ttl_seconds": PAIRING_TTL_SECONDS,
        "qr_payload": qr_payload,
    }


def _validate_pending(code: str, token: str) -> Dict[str, Any]:
    with _lock:
        pending = _pending_codes.get(code)
        if not pending:
            raise HTTPException(status_code=404, detail="pairing code not found or already used")
        if code in _paired_codes:
            raise HTTPException(status_code=409, detail="pairing code already used")
        if time.time() > pending["expires_at"]:
            _pending_codes.pop(code, None)
            raise HTTPException(status_code=410, detail="pairing code expired")
        expected = pending["token"]
        if not hmac.compare_digest(str(token or ""), expected):
            raise HTTPException(status_code=401, detail="pairing token mismatch")
        return pending


def consume_pairing_code(
    code: str, token: str, device_id: str, device_name: str
) -> Dict[str, Any]:
    """Canjea el código (un solo uso), registra y aprueba el dispositivo móvil."""
    _validate_pending(code, token)

    from backend.device_auth import DeviceAuthManager

    manager = DeviceAuthManager.get_instance()
    reg = manager.register_device(device_id, device_name)
    approved = manager.approve_device(device_id)
    if not approved:
        # Rollback del registro para no dejar dispositivos pendientes huérfanos.
        manager.revoke_device(device_id)
        raise HTTPException(status_code=500, detail="could not approve paired device")

    with _lock:
        _paired_codes.add(code)
        _pending_codes.pop(code, None)

    host_ip = get_local_ip()
    return {
        "status": "paired",
        "device_id": device_id,
        "device_token": reg["token"],
        "expires_in": reg.get("expires_in"),
        "backend_url": f"http://{host_ip}:{os.getenv('AURA_PORT', '8000')}",
        "paired_at": time.time(),
    }


@router.get("/profile")
async def pairing_profile() -> Dict[str, Any]:
    """Perfil de emparejamiento local (IP + código + token firmado + QR)."""
    return create_pairing_profile(int(os.getenv("AURA_PORT", "8000")))


@router.post("/handshake")
async def pairing_handshake(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Canjea el código de emparejamiento y devuelve el token de dispositivo."""
    qr_payload = str(payload.get("qr_payload", "")).strip()
    code = str(payload.get("code", "")).strip()
    token = str(payload.get("token", "")).strip()

    if qr_payload and not code:
        parsed = _code_from_qr_payload(qr_payload)
        if not parsed:
            raise HTTPException(status_code=422, detail="invalid qr_payload")
        code = str(parsed.get("code", ""))
        token = str(parsed.get("token", ""))

    device_id = str(payload.get("device_id", "")).strip()
    device_name = str(payload.get("device_name", "")).strip() or "AME Mobile"
    if not code or not token:
        raise HTTPException(status_code=422, detail="code and token are required")
    if not device_id:
        device_id = f"ame_{secrets.token_hex(4)}"

    return consume_pairing_code(code, token, device_id, device_name)


@router.get("/ping")
async def pairing_ping() -> Dict[str, Any]:
    """Health-check de latencia LAN para el cliente móvil."""
    return {"ok": True, "ts": time.time(), "service": "aura-host"}