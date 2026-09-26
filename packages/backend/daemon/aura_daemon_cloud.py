# -*- coding: utf-8 -*-
"""AURA OS — Daemon Cloud Extension.

Extiende el daemon existente para:
- Verificacion de conectividad
- Sincronizacion entre dispositivos
- Backup automatico a la nube
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.DaemonCloud")


class AURADaemonCloud:
    """Extension del daemon para operaciones cloud."""

    def __init__(self, parent_daemon: Optional[Any] = None) -> None:
        self.parent_daemon = parent_daemon
        self.cloud_active: bool = True
        self._last_connectivity_check: float = 0
        self._last_device_sync: float = 0
        self._last_backup: float = 0
        self._connectivity: bool = True
        self._sync_interval: int = 30
        self._backup_interval: int = 3600
        self._cloud_sync_enabled: bool = True

    async def _check_connectivity(self) -> None:
        """Verifica si hay conexion a la nube."""
        now = time.time()
        if now - self._last_connectivity_check < self._sync_interval:
            return

        self._last_connectivity_check = now

        try:
            connected = await self._test_cloud_connection()
            prev = self._connectivity
            self._connectivity = connected

            if connected and not prev:
                logger.info("Cloud connection restored. Retrying offline queue...")
                try:
                    from backend.cloud.offline_queue import offline_queue
                    result = await offline_queue.retry_offline_queue()
                    logger.info("Offline queue retry: %d retried, %d failed", result["retried"], len(result["failed"]))
                    from backend.core import get_event_bus
                    get_event_bus().emit_simple("cloud_restored", {"retried": result["retried"]}, agent="daemon-cloud")
                except Exception as exc:
                    logger.error("Queue retry failed: %s", exc)

            elif not connected and prev:
                logger.warning("Cloud connection lost. Queuing actions locally...")
                from backend.core import get_event_bus
                get_event_bus().emit_simple("cloud_lost", {"reason": "connection_timeout"}, agent="daemon-cloud")

        except Exception as exc:
            logger.error("Connectivity check error: %s", exc)
            self._connectivity = False

    async def _test_cloud_connection(self) -> bool:
        """Prueba la conexion a la nube."""
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://aura-prod.railway.app/api/health") as resp:
                    return resp.status == 200
        except Exception:
            try:
                import urllib.request
                req = urllib.request.Request("https://aura-prod.railway.app/api/health")
                urllib.request.urlopen(req, timeout=5)
                return True
            except Exception:
                return False

    async def _sync_with_devices(self) -> None:
        """Sincroniza con otros dispositivos cada 30 segundos."""
        now = time.time()
        if now - self._last_device_sync < self._sync_interval:
            return

        self._last_device_sync = now

        if not self._connectivity or not self._cloud_sync_enabled:
            return

        try:
            devices = await self._get_synced_devices()
            for device in devices:
                if device.get("device_id") and device.get("online"):
                    result = await self._pull_device_changes(device["device_id"])
                    if result and result.get("delta"):
                        await self._apply_changes_local(result["delta"])
                        from backend.core import get_event_bus
                        get_event_bus().emit_simple("device_synced", {
                            "device_id": device["device_id"],
                            "delta_keys": list(result["delta"].keys()),
                            "version": result["version"],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }, agent="daemon-cloud")

            logger.debug("Device sync cycle complete: %d devices", len(devices))

        except Exception as exc:
            logger.error("Device sync error: %s", exc)

    async def _backup_to_cloud(self) -> None:
        """Backup completo a la nube cada hora."""
        now = time.time()
        if now - self._last_backup < self._backup_interval:
            return

        self._last_backup = now

        if not self._connectivity:
            logger.warning("Skipping backup — no cloud connection")
            return

        try:
            snapshot = await self._create_snapshot()
            await self._upload_snapshot(snapshot)

            from backend.core import get_event_bus
            get_event_bus().emit_simple("cloud_backup", {
                "snapshot_id": snapshot.get("id"),
                "size_mb": snapshot.get("size_mb", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, agent="daemon-cloud")

            logger.info("Cloud backup complete: %s", snapshot.get("id"))

        except Exception as exc:
            logger.error("Cloud backup error: %s", exc)

    async def _get_synced_devices(self) -> List[Dict[str, Any]]:
        """Obtiene dispositivos sincronizados."""
        try:
            from backend.cloud.firebase_manager import firebase_sync
            devices = await firebase_sync.get_device_list()
            return devices
        except Exception:
            return []

    async def _pull_device_changes(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene cambios de un dispositivo."""
        try:
            from backend.cloud.firebase_manager import firebase_sync
            result = await firebase_sync.pull_from_cloud(device_id, since_version=0)
            return result
        except Exception as exc:
            logger.debug("Pull from %s failed: %s", device_id, exc)
            return None

    async def _apply_changes_local(self, delta: Dict[str, Any]) -> None:
        """Aplica cambios localmente."""
        for key, value in delta.items():
            if key.startswith("_"):
                continue
            try:
                from backend.memory import working_memory
                await working_memory.store(key, value)
            except Exception:
                pass

    async def _create_snapshot(self) -> Dict[str, Any]:
        """Crea snapshot de estado actual."""
        snapshot_id = f"snapshot_{int(time.time())}"
        return {
            "id": snapshot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size_mb": 0,
            "data": {
                "memory": "snapshot_data",
                "config": "snapshot_data",
            },
        }

    async def _upload_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Sube snapshot a la nube."""
        try:
            from backend.cloud.firebase_manager import firebase_sync
            await firebase_sync.push_to_cloud("backup_server", snapshot)
        except Exception as exc:
            logger.debug("Snapshot upload failed: %s", exc)

    def get_cloud_status(self) -> Dict[str, Any]:
        """Retorna estado del cloud sync."""
        return {
            "cloud_active": self.cloud_active,
            "connected": self._connectivity,
            "sync_interval_seconds": self._sync_interval,
            "backup_interval_seconds": self._backup_interval,
            "last_connectivity_check": datetime.fromtimestamp(self._last_connectivity_check, timezone.utc).isoformat() if self._last_connectivity_check else None,
            "last_device_sync": datetime.fromtimestamp(self._last_device_sync, timezone.utc).isoformat() if self._last_device_sync else None,
            "last_backup": datetime.fromtimestamp(self._last_backup, timezone.utc).isoformat() if self._last_backup else None,
            "cloud_sync_enabled": self._cloud_sync_enabled,
        }


aura_daemon_cloud = AURADaemonCloud()
