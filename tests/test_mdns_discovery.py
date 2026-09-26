"""Tests Bloque 35 — mDNS Zero-Config Discovery (paquetes de anuncio de red).

Valida (sin tocar la red/multicast real):
- SERVICE_TYPE estándar ``_aura-host._tcp.local`` y metadatos del anuncio.
- build_service_info: construye el paquete de anuncio con la IP local real.
- resolve_local_ip / get_all_local_ips: resolución de interfaces (mockeadas).
- parse_manual_hosts: fallback manual vía AURA_HOST_IPS / TAILSCALE_IP.
- MDNSDiscovery.start()/stop()/get_discovered_hosts() y discover() con
  Zeroconf/ServiceBrowser mockeados (fallback cuando el multicast falla).
- discover_hosts() / get_local_ips() (helpers REST).
"""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

import backend.mobile.discovery as disc
from backend.mobile.discovery import (
    DEFAULT_PORT,
    SERVICE_LABEL,
    SERVICE_TYPE,
    MDNSDiscovery,
    build_service_info,
    discover_hosts,
    get_all_local_ips,
    get_local_ips,
    parse_manual_hosts,
    resolve_local_ip,
)

# -- Constantes del servicio estándar ------------------------------------------


def test_service_type_is_standard_aura_host():
    assert SERVICE_TYPE == "_aura-host._tcp.local."
    assert SERVICE_TYPE.startswith("_") and SERVICE_TYPE.endswith("._tcp.local.")
    assert SERVICE_LABEL == "AURA OS"
    assert DEFAULT_PORT == 8000


# -- build_service_info (paquete de anuncio) ------------------------------------


def test_build_service_info_announces_real_local_ip():
    """El anuncio usa la IP local real (no 0.0.0.0) y el tipo estándar."""
    with patch.object(disc, "resolve_local_ip", return_value="192.168.1.50"):
        info = build_service_info("AURA OS", 8000)
    assert info.type == SERVICE_TYPE
    assert info.port == 8000
    assert info.name.startswith("AURA OS._aura-host._tcp.local.")
    addr = socket.inet_ntoa(info.addresses[0])
    assert addr == "192.168.1.50"
    props = {
        k.decode() if isinstance(k, bytes) else k: (v.decode() if isinstance(v, bytes) else v)
        for k, v in info.properties.items()
    }
    assert props["name"] == "AURA OS"
    assert props["port"] == "8000"
    assert "version" in props


def test_build_service_info_falls_back_to_wildcard_ip():
    """Si resolve_local_ip falla (0.0.0.0), el anuncio no se rompe."""
    with patch.object(disc, "resolve_local_ip", return_value="0.0.0.0"):
        info = build_service_info("AURA OS", 8000)
    assert info.port == 8000
    assert socket.inet_ntoa(info.addresses[0]) == "0.0.0.0"


def test_build_service_info_custom_properties_merged():
    with patch.object(disc, "resolve_local_ip", return_value="10.0.0.5"):
        info = build_service_info("AURA OS", 8000, properties={"node": "pc-01"})
    props = {
        k.decode() if isinstance(k, bytes) else k: (v.decode() if isinstance(v, bytes) else v)
        for k, v in info.properties.items()
    }
    assert props["node"] == "pc-01"


# -- Fallback manual -------------------------------------------------------------


def test_parse_manual_hosts_from_env(monkeypatch):
    monkeypatch.setenv("AURA_HOST_IPS", "192.168.1.50, 10.0.0.5")
    monkeypatch.setenv("TAILSCALE_IP", "100.101.102.103")
    hosts = parse_manual_hosts()
    assert hosts == ["192.168.1.50", "10.0.0.5", "100.101.102.103"]


def test_parse_manual_hosts_empty_by_default(monkeypatch):
    monkeypatch.delenv("AURA_HOST_IPS", raising=False)
    monkeypatch.delenv("TAILSCALE_IP", raising=False)
    assert parse_manual_hosts() == []


def test_parse_manual_hosts_dedupes_tailscale(monkeypatch):
    monkeypatch.setenv("AURA_HOST_IPS", "100.64.0.1")
    monkeypatch.setenv("TAILSCALE_IP", "100.64.0.1")
    assert parse_manual_hosts() == ["100.64.0.1"]


# -- Resolución de interfaces (mockeada) -------------------------------------------


def test_resolve_local_ip_via_udp_then_hostname():
    with (
        patch.object(disc.socket.socket, "connect", side_effect=OSError),
        patch.object(disc.socket, "gethostname", return_value="pc"),
        patch.object(disc.socket, "gethostbyname", return_value="192.168.1.77"),
    ):
        assert resolve_local_ip() == "192.168.1.77"


def test_resolve_local_ip_returns_wildcard_on_total_failure():
    with (
        patch.object(disc.socket.socket, "connect", side_effect=OSError),
        patch.object(disc.socket, "gethostname", side_effect=OSError),
    ):
        assert resolve_local_ip() == "0.0.0.0"


def test_get_all_local_ips_excludes_loopback():
    with (
        patch.object(disc.socket, "gethostname", return_value="pc"),
        patch.object(
            disc.socket, "gethostbyname_ex", return_value=("pc", [], ["127.0.0.1", "192.168.1.50"])
        ),
        patch.object(disc, "resolve_local_ip", return_value="192.168.1.50"),
    ):
        ips = get_all_local_ips()
    assert "192.168.1.50" in ips
    assert "127.0.0.1" not in ips


# -- MDNSDiscovery -------------------------------------------------------------------


class _FakeZeroconf:
    """Zeroconf simulado: registra/cancela sin red."""

    def __init__(self, *a, **kw):
        self.registered: list = []

    def register_service(self, info, *a, **kw):
        self.registered.append(info)

    def unregister_service(self, info, *a, **kw):
        if self.registered:
            self.registered.remove(info)

    def close(self):
        pass


def test_mdns_start_and_stop_lifecycle(monkeypatch):
    inst = MDNSDiscovery(name="AURA OS", port=8000)
    assert inst.configured is False
    monkeypatch.setattr(disc, "Zeroconf", _FakeZeroconf)
    with patch.object(disc, "resolve_local_ip", return_value="192.168.1.50"):
        ret = inst.start()
    assert ret is inst
    assert inst.configured is True
    assert len(inst._zeroconf.registered) == 1
    inst.stop()
    assert inst.configured is False


def test_mdns_start_is_idempotent(monkeypatch):
    inst = MDNSDiscovery()
    monkeypatch.setattr(disc, "Zeroconf", _FakeZeroconf)
    with patch.object(disc, "resolve_local_ip", return_value="192.168.1.50"):
        inst.start()
        first = inst._zeroconf
        inst.start()  # segunda llamada no recrea el servicio
    assert inst._zeroconf is first


def test_get_discovered_hosts_includes_manual_fallback(monkeypatch):
    monkeypatch.setenv("AURA_HOST_IPS", "10.0.0.9")
    inst = MDNSDiscovery(port=8000)
    inst._discovered["hostA._aura-host._tcp.local."] = {
        "address": "192.168.1.50",
        "port": 8000,
        "properties": {"name": "AURA OS"},
    }
    hosts = inst.get_discovered_hosts()
    assert "hostA._aura-host._tcp.local." in hosts
    assert hosts["manual-10.0.0.9"]["address"] == "10.0.0.9"
    assert hosts["manual-10.0.0.9"]["port"] == 8000
    # El fallback manual nunca expone secretos.
    assert "token" not in str(hosts).lower()


def test_discover_merges_manual_hosts_when_multicast_empty(monkeypatch):
    """Si el multicast no encuentra nada, discover() retorna los hosts manuales."""
    monkeypatch.setenv("AURA_HOST_IPS", "10.0.0.9")

    inst = MDNSDiscovery(port=8000)
    monkeypatch.setattr(disc, "Zeroconf", _FakeZeroconf)
    monkeypatch.setattr(disc, "ServiceBrowser", lambda zc, stype, handlers=None: MagicMock())
    with patch("time.sleep", lambda s: None):
        hosts = inst.discover(timeout=0.01)
    assert hosts["manual-10.0.0.9"]["address"] == "10.0.0.9"


def test_extract_address_handles_ipv4_and_ipv6():
    inst = MDNSDiscovery()
    v4 = MagicMock()
    v4.addresses = [socket.inet_aton("192.168.1.50")]
    assert inst._extract_address(v4) == "192.168.1.50"

    v6 = MagicMock()
    v6.addresses = [socket.inet_pton(socket.AF_INET6, "fe80::1")]
    assert inst._extract_address(v6) == "fe80::1"

    none = MagicMock()
    none.addresses = []
    assert inst._extract_address(none) == "unknown"


# -- Helpers REST ---------------------------------------------------------------------


def test_get_local_ips_delegates():
    with patch.object(disc, "get_all_local_ips", return_value=["192.168.1.50"]):
        assert get_local_ips() == ["192.168.1.50"]


def test_discover_hosts_delegates_to_singleton(monkeypatch):
    monkeypatch.setenv("AURA_HOST_IPS", "10.0.0.9")
    with (
        patch.object(disc, "Zeroconf", _FakeZeroconf),
        patch.object(disc, "ServiceBrowser", lambda zc, stype, handlers=None: MagicMock()),
        patch("time.sleep", lambda s: None),
    ):
        hosts = discover_hosts(timeout=0.01)
    assert hosts["manual-10.0.0.9"]["address"] == "10.0.0.9"
