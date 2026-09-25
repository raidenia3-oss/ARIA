"""Cross-device synchronization daemon."""
from __future__ import annotations
import logging

logger = logging.getLogger("aria.daemon.sync")


class CrossDeviceSync:
    """Sincroniza datos entre dispositivos."""

    def __init__(self) -> None:
        self._peers: list[str] = []
        self.nodes: dict[str, Any] = {}  # Empty dict for compatibility with app.py

    async def sync(self) -> bool:
        logger.info("Cross-device sync started")
        return True
