"""Local network gateway for AURA - Module 27.

Descubrimiento de instancias AURA en LAN, generacion de tokens de
emparejamiento para dispositivos moviles y API de túnel local seguro.
"""

from __future__ import annotations

import ipaddress
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PairingToken:
    token: str
    device_name: str
    created_at: float
    expires_at: float
    status: str = "pending"
    client_info: Dict[str, Any] = field(default_factory=dict)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token": self.token,
            "device_name": self.device_name,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "expired": self.expired,
            "client_info": self.client_info,
        }


class LanDiscoveryService:
    """Descubrimiento de instancias AURA en la red local via UDP broadcast."""

    SERVICE_PORT = 8899
    DISCOVERY_INTERVAL = 30

    def __init__(self, local_port: int = 8000) -> None:
        self.local_port = local_port
        self.broadcast_port = self.SERVICE_PORT
        self.discovered: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_local_ip_and_port(self) -> Dict[str, Any]:
        return {"host": self.get_local_ip(), "port": self.local_port}

    def broadcast_discovery(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        packet = json.dumps({
            "service": "aura",
            "port": self.local_port,
            "host": self.get_local_ip(),
            "timestamp": time.time(),
        }).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        responses: List[Dict[str, Any]] = []
        try:
            sock.sendto(packet, ("<broadcast>", self.broadcast_port))
            while True:
                try:
                    data, addr = sock.recvfrom(4096)
                    info = json.loads(data.decode("utf-8"))
                    self.discovered[addr[0]] = info
                    responses.append({"address": addr[0], "info": info})
                except socket.timeout:
                    break
        except Exception:
            pass
        finally:
            sock.close()
        return responses

    def start_broadcast_loop(self, interval: float = None) -> None:
        if self._running:
            return
        self._running = True
        interval = interval or self.DISCOVERY_INTERVAL

        def loop() -> None:
            while self._running:
                try:
                    self.broadcast_discovery(timeout=2.0)
                except Exception:
                    pass
                time.sleep(interval)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "local_ip": self.get_local_ip(),
            "local_port": self.local_port,
            "broadcast_port": self.broadcast_port,
            "discovered_count": len(self.discovered),
            "discovered_instances": [
                {"address": addr, "info": info} for addr, info in self.discovered.items()
            ],
        }


class MobilePairingEngine:
    """Generación y validacion de tokens de emparejamiento para moviles."""

    def __init__(self, default_expires_in: int = 300) -> None:
        self.tokens: Dict[str, PairingToken] = {}
        self.default_expires_in = default_expires_in
        self._lock = threading.RLock()

    def generate_token(self, device_name: str = "mobile-device", expires_in: Optional[int] = None) -> Dict[str, Any]:
        token = secrets.token_urlsafe(32)
        expires = time.time() + (expires_in or self.default_expires_in)
        with self._lock:
            self.tokens[token] = PairingToken(
                token=token,
                device_name=device_name,
                created_at=time.time(),
                expires_at=expires,
            )
        return {
            "token": token,
            "device_name": device_name,
            "expires_at": expires,
            "pairing_url": f"aura://pair/{token}",
            "qr_payload": json.dumps({"token": token, "service": "aura"}),
        }

    def validate_token(self, token: str) -> Dict[str, Any]:
        pt = self.tokens.get(token)
        if not pt:
            return {"valid": False, "error": "token_not_found"}
        if pt.expired:
            pt.status = "expired"
            return {"valid": False, "error": "token_expired"}
        return {
            "valid": True,
            "device_name": pt.device_name,
            "status": pt.status,
            "expires_at": pt.expires_at,
            "pairing_url": f"aura://pair/{token}",
        }

    def pair(self, token: str, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            pt = self.tokens.get(token)
            if not pt or pt.expired:
                return {"status": "failed", "error": "invalid_or_expired_token"}
            pt.status = "paired"
            if client_info:
                pt.client_info = client_info
        return {"status": "paired", "device_name": pt.device_name, "token": token}

    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [t for t, pt in self.tokens.items() if pt.expired]
            for t in expired:
                del self.tokens[t]
        return len(expired)

    def status(self) -> Dict[str, Any]:
        active = sum(1 for pt in self.tokens.values() if not pt.expired)
        paired = sum(1 for pt in self.tokens.values() if pt.status == "paired")
        return {
            "total_tokens": len(self.tokens),
            "active_tokens": active,
            "paired_tokens": paired,
            "expired_tokens": len(self.tokens) - active,
        }

    def get_token(self, token: str) -> Optional[Dict[str, Any]]:
        pt = self.tokens.get(token)
        if not pt or pt.expired:
            return None
        return pt.to_dict()


class LocalNetworkGateway:
    """Túnel local seguro y API para clientes remotos sin exponer puertos públicos."""

    def __init__(self, local_port: int = 8000) -> None:
        self.discovery = LanDiscoveryService(local_port=local_port)
        self.pairing = MobilePairingEngine()
        self.api_tokens: Dict[str, Dict[str, Any]] = {}
        self._started = False

    def start(self) -> Dict[str, Any]:
        if not self._started:
            self.discovery.start_broadcast_loop()
            self._started = True
        self.pairing.cleanup_expired()
        return {
            "status": "started",
            "local_endpoint": self.discovery.get_local_ip_and_port(),
            "pairing_ready": True,
        }

    def stop(self) -> None:
        self._started = False
        self.discovery.stop()

    def get_pairing_token(self, device_name: str = "mobile-device", expires_in: Optional[int] = None) -> Dict[str, Any]:
        return self.pairing.generate_token(device_name, expires_in)

    def validate_pairing(self, token: str) -> Dict[str, Any]:
        return self.pairing.validate_token(token)

    def pair_device(self, token: str, client_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.pairing.pair(token, client_info)

    def generate_api_token(self, device_name: str = "remote-client") -> Dict[str, Any]:
        token = secrets.token_urlsafe(48)
        self.api_tokens[token] = {
            "device_name": device_name,
            "created_at": time.time(),
            "expires_at": time.time() + 86400,
        }
        return {"api_token": token, "expires_at": self.api_tokens[token]["expires_at"]}

    def validate_api_token(self, token: str) -> bool:
        entry = self.api_tokens.get(token)
        if not entry or time.time() > entry["expires_at"]:
            return False
        return True

    def discover(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        return self.discovery.broadcast_discovery(timeout=timeout)

    def status(self) -> Dict[str, Any]:
        return {
            "started": self._started,
            "local_endpoint": self.discovery.get_local_ip_and_port(),
            "discovery": self.discovery.status(),
            "pairing": self.pairing.status(),
            "api_tokens_active": sum(
                1 for t in self.api_tokens.values() if time.time() <= t["expires_at"]
            ),
        }
