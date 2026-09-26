import logging
import socket
import threading
from typing import Any, Dict, Optional

from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf

logger = logging.getLogger("ARIA.mobile.discovery")

SERVICE_TYPE = "_aura._tcp.local."


class MDNSDiscovery:
    """mDNS discovery for AURA mobile sync via Zeroconf/avahi."""

    def __init__(self, name: str = "ARIA OS", port: int = 8000):
        self.name = name
        self.port = port
        self._zeroconf: Optional[Zeroconf] = None
        self._service_info: Optional[ServiceInfo] = None
        self._discovered: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def start(self):
        """Broadcast this AURA instance via mDNS."""
        if self._zeroconf is not None:
            logger.info("mDNS already started")
            return

        desc = {"version": "2.0.0", "name": self.name}
        self._zeroconf = Zeroconf()
        self._service_info = ServiceInfo(
            type_=SERVICE_TYPE,
            name=f"{self.name}._aura._tcp.local.",
            addresses=[socket.inet_aton("0.0.0.0")],
            port=self.port,
            properties=desc,
        )
        self._zeroconf.register_service(self._service_info)
        logger.info("mDNS service registered: %s on port %d", self.name, self.port)

    def stop(self):
        """Unregister mDNS service."""
        if self._zeroconf and self._service_info:
            try:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
            except Exception as exc:
                logger.warning("mDNS unregister error: %s", exc)
            finally:
                self._zeroconf = None
                self._service_info = None
                logger.info("mDNS service stopped")

    def discover(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Discover other AURA instances on the local network."""
        if not self._zeroconf:
            self._zeroconf = Zeroconf()

        def on_service_state_change(zc, service_type, name, state_change):
            if state_change.name == "Add":
                info = zc.get_service_info(service_type, name)
                if info:
                    addr = socket.inet_ntoa(info.addresses[0]) if info.addresses else "unknown"
                    with self._lock:
                        self._discovered[name] = {
                            "address": addr,
                            "port": info.port,
                            "properties": {
                                k.decode(): v.decode() for k, v in info.properties.items()
                            },
                        }

        browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, handlers=[on_service_state_change])
        import time

        time.sleep(timeout)
        browser.cancel()
        return self._discovered.copy()


mdns = MDNSDiscovery()


def start_mdns(name: str = "ARIA OS", port: int = 8000) -> MDNSDiscovery:
    """Start a new mDNS discovery instance."""
    instance = MDNSDiscovery(name=name, port=port)
    instance.start()
    return instance


def stop_mdns(instance: MDNSDiscovery):
    """Stop an mDNS discovery instance."""
    instance.stop()
