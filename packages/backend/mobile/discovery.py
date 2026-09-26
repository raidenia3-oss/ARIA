"""AURA Local mDNS Zero-Config Discovery & Network Auto-Binding.

Servicio de autodescubrimiento en red local basado en mDNS (Multicast DNS
/ Bonjour) que permite a la aplicación móvil AME detectar de forma automática
y transparente el host de AURA en la PC sin necesidad de configurar direcciones
IP manuales ni escanear códigos QR repetidamente.

Diseño:
- Nombre de servicio estándar: ``_aura-host._tcp.local`` (RFC 6763).
- El backend anuncia su IP local real + puerto activo vía ``zeroconf``.
- Endpoint REST ``/api/mobile/discover`` expone los hosts descubiertos como
  fallback para entornos donde el multicast está bloqueado.
- Fallback manual: variables de entorno ``AURA_HOST_IPS`` (lista separada por
  comas) o ``TAILSCALE_IP`` para redes donde mDNS no funciona.
- Los tokens nunca se exponen: el endpoint ``/api/mobile/discovery`` sigue
  siendo la fuente de truth para el pairing token.

Compatibilidad:
- Mantiene la interfaz legacy ``MDNSDiscovery`` / ``mdns`` / ``start_mdns`` /
  ``stop_mdns`` usada por ``backend/main.py``.
- ``start()`` / ``stop()`` son síncronos (zeroconf no es async) pero seguros
  para llamar desde un ``async def`` (no bloquean el event loop significativamente).
- ``discover()`` retorna un dict serializable con los hosts encontrados.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from typing import Any, Dict, List, Optional, Tuple

from zeroconf import IPVersion, ServiceInfo, ServiceBrowser, Zeroconf

logger = logging.getLogger("aura.mobile.discovery")

# Nombre de servicio mDNS estándar (RFC 6763).
SERVICE_TYPE = "_aura-host._tcp.local."
SERVICE_LABEL = "AURA OS"
DEFAULT_PORT = 8000

# Fallback manual configurable vía env (no se committea).
# Formato: "192.168.1.50,10.0.0.5" (comas) o una IP de Tailscale.
_FALLBACK_ENV = "AURA_HOST_IPS"
_TAILSCALE_ENV = "TAILSCALE_IP"


def resolve_local_ip() -> str:
    """Resuelve la IP local de la interfaz de red primaria (no 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception as exc:  # noqa: BLE001
        logger.debug("UDP connect fallback failed: %s", exc)
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip and not local_ip.startswith("127."):
            return local_ip
    except Exception as exc:  # noqa: BLE001
        logger.debug("gethostname fallback failed: %s", exc)
    return "0.0.0.0"


def get_all_local_ips() -> List[str]:
    """Lista todas las IPs de interfaces de red locales (excluye loopback)."""
    ips: List[str] = []
    try:
        hostname = socket.gethostname()
        all_ips = socket.gethostbyname_ex(hostname)
        for ip in all_ips[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception as exc:  # noqa: BLE001
        logger.debug("gethostbyname_ex failed: %s", exc)
    fallback = resolve_local_ip()
    if fallback and fallback != "0.0.0.0" and fallback not in ips:
        ips.append(fallback)
    if not ips:
        ips.append("127.0.0.1")
    return ips


def parse_manual_hosts() -> List[str]:
    """Lee hosts manuales desde AURA_HOST_IPS (coma-separados) y TAILSCALE_IP."""
    hosts: List[str] = []
    raw = _get_env(_FALLBACK_ENV)
    if raw:
        for part in raw.split(","):
            ip = part.strip()
            if ip:
                hosts.append(ip)
    ts_ip = _get_env(_TAILSCALE_ENV)
    if ts_ip and ts_ip not in hosts:
        hosts.append(ts_ip)
    return hosts


def _get_env(key: str) -> Optional[str]:
    import os
    return os.getenv(key)


def build_service_info(name: str, port: int, properties: Optional[Dict[str, str]] = None) -> ServiceInfo:
    """Construye un ServiceInfo con la IP local real (no 0.0.0.0)."""
    local_ip = resolve_local_ip()
    try:
        ip_bytes = socket.inet_pton(socket.AF_INET, local_ip)
    except OSError:
        ip_bytes = socket.inet_aton("0.0.0.0")

    desc = {
        "version": "2.1.0",
        "name": name or SERVICE_LABEL,
        "port": str(port),
        **(properties or {}),
    }
    return ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{name or SERVICE_LABEL}._aura-host._tcp.local.",
        addresses=[ip_bytes],
        port=port,
        weight=0,
        priority=0,
        properties=desc,
    )


class MDNSDiscovery:
    """Servicio de autodescubrimiento mDNS para AURA / AME.

    - ``start()``: anuncia el host AURA en la red local vía mDNS.
    - ``stop()``: desregistra el servicio.
    - ``discover(timeout)``: escanea la red local y retorna hosts AURA encontrados.
    - ``get_discovered_hosts()``: retorna el dict de hosts descubiertos (cache).
    """

    def __init__(self, name: str = SERVICE_LABEL, port: int = DEFAULT_PORT):
        self.name = name
        self.port = port
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._discovered: Dict[str, Any] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        """True si la instancia está anunciando o puede descubrir."""
        return self._zeroconf is not None

    def start(self) -> "MDNSDiscovery":
        """Anuncia este host AURA en la red local vía mDNS."""
        if self._zeroconf is not None:
            logger.info("mDNS already started")
            return self

        info = build_service_info(self.name, self.port)
        self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self._zeroconf.register_service(info)
        self._service_info = info
        local_ip = resolve_local_ip()
        logger.info("mDNS service registered: %s on %s:%d", SERVICE_TYPE, local_ip, self.port)
        return self

    def stop(self) -> None:
        """Desregistra el servicio mDNS."""
        if self._zeroconf and self._service_info:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
                logger.info("mDNS service stopped")
            except Exception as exc:  # noqa: BLE001
                logger.warning("mDNS unregister error: %s", exc)
            finally:
                self._zeroconf = None
                self._service_info = None
        else:
            self._zeroconf = None
            self._service_info = None

    def discover(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Descubre instancias AURA en la red local (blocking, best-effort).

        Si el multicast falla, retorna los hosts manuales configurados vía env.
        """
        manual_hosts = parse_manual_hosts()
        if self._zeroconf is None:
            self._zeroconf = Zeroconf(ip_version=IPVersion.V4Only)

        self._discovered.clear()
        browser = ServiceBrowser(
            self._zeroconf, SERVICE_TYPE, handlers=[self._on_service_state_change]
        )
        try:
            import time
            time.sleep(timeout)
        finally:
            browser.cancel()

        # Añadir hosts manuales como fallback
        for manual_ip in manual_hosts:
            self._discovered[f"manual-{manual_ip}"] = {
                "address": manual_ip,
                "port": self.port,
                "properties": {
                    "version": "2.1.0",
                    "name": "manual",
                    "type": "manual",
                },
            }
        return dict(self._discovered)

    def _on_service_state_change(self, zc: Zeroconf, service_type: str, name: str, state_change) -> None:
        if state_change.name == "Add":
            info = zc.get_service_info(service_type, name, timeout=3000)
            if info:
                addr = self._extract_address(info)
                with self._lock:
                    self._discovered[name] = {
                        "address": addr,
                        "port": info.port,
                        "properties": {
                            k.decode(errors="replace") if isinstance(k, bytes) else k: (
                                v.decode(errors="replace") if isinstance(v, bytes) else v
                            )
                            for k, v in info.properties.items()
                        },
                    }

    def _extract_address(self, info: ServiceInfo) -> str:
        """Extrae la primera IP válida de una ServiceInfo."""
        if info.addresses:
            for raw in info.addresses:
                try:
                    if len(raw) == 4:
                        return socket.inet_ntoa(raw)
                    elif len(raw) == 16:
                        return socket.inet_ntop(socket.AF_INET6, raw)
                except (ValueError, OSError):
                    continue
        return "unknown"

    def get_discovered_hosts(self) -> Dict[str, Any]:
        """Retorna el cache de hosts descubiertos (incluye manual fallback)."""
        with self._lock:
            result = dict(self._discovered)
        for manual_ip in parse_manual_hosts():
            key = f"manual-{manual_ip}"
            if key not in result:
                result[key] = {
                    "address": manual_ip,
                    "port": self.port,
                    "properties": {"name": "manual", "type": "manual"},
                }
        return result

    @property
    def addresses(self) -> List[str]:
        """Lista de IPs locales anunciadas."""
        return get_all_local_ips()


mdns = MDNSDiscovery()


def start_mdns(name: str = SERVICE_LABEL, port: int = DEFAULT_PORT) -> MDNSDiscovery:
    """Start a new mDNS discovery instance."""
    instance = MDNSDiscovery(name=name, port=port)
    instance.start()
    return instance


def stop_mdns(instance: Optional[MDNSDiscovery] = None) -> None:
    """Stop an mDNS discovery instance (defaults to the global singleton)."""
    if instance is None:
        instance = mdns
    instance.stop()


def discover_hosts(timeout: float = 3.0) -> Dict[str, Any]:
    """Función de conveniencia: descubre hosts AURA en la red local."""
    return mdns.discover(timeout=timeout)


def get_local_ips() -> List[str]:
    """Retorna las IPs locales del host (para uso por endpoints REST)."""
    return get_all_local_ips()
