"""BLOQUE 69/78 - AURA Network Proxy & Mesh P2P package."""
from backend.network.mesh import (
    MeshNode,
    MeshOrchestrator,
    MeshPacket,
    P2PMeshEngine,
    SwarmStateSnapshot,
    get_mesh_orchestrator,
    reset_mesh_orchestrator,
)

try:  # proxy engine is optional/broken in this snapshot
    from backend.network.proxy import (  # type: ignore
        NetworkProxy,
        NetworkProxyEngine,
        proxy_engine,
        ProxyCertificateManager,
        WebSocketProxySession,
    )
except Exception:  # pragma: no cover - defensive
    NetworkProxy = NetworkProxyEngine = proxy_engine = None
    WebSocketProxySession = None
    ProxyCertificateManager = None

from backend.network.models import (
    ProxyConfig,
    InterceptRule,
    TrafficEntry,
    PayloadManipulation,
    CertificateInfo,
    WebSocketProxyConfig,
    ProxyMode,
    InterceptAction,
    ProtocolFilter,
)

__all__ = [
    "NetworkProxy",
    "NetworkProxyEngine",
    "proxy_engine",
    "ProxyCertificateManager",
    "WebSocketProxySession",
    "ProxyConfig",
    "InterceptRule",
    "TrafficEntry",
    "PayloadManipulation",
    "CertificateInfo",
    "WebSocketProxyConfig",
    "ProxyMode",
    "InterceptAction",
    "ProtocolFilter",
    "MeshNode",
    "MeshOrchestrator",
    "MeshPacket",
    "P2PMeshEngine",
    "SwarmStateSnapshot",
    "get_mesh_orchestrator",
    "reset_mesh_orchestrator",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
