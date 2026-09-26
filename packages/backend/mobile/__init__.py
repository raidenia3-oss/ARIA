from backend.mobile.discovery import (
    mdns,
    MDNSDiscovery,
    start_mdns,
    stop_mdns,
    discover_hosts,
    get_local_ips,
)
from backend.mobile.sync import sync_manager, mobile_sync, SyncEvent
from backend.mobile.ame_client import AMEClient, test_ame_sync

__all__ = [
    "mdns",
    "MDNSDiscovery",
    "start_mdns",
    "stop_mdns",
    "discover_hosts",
    "get_local_ips",
    "sync_manager",
    "mobile_sync",
    "SyncEvent",
    "AMEClient",
    "test_ame_sync",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
