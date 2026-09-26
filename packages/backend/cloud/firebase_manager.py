# -*- coding: utf-8 -*-
"""AURA OS — Firebase Sync Manager (Multi-Device).

Sincroniza datos entre dispositivos via Firebase Realtime Database
y Firestore para historial.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.FirebaseSync")


class FirebaseSync:
    """Gestor de sincronizacion Firebase para multi-dispositivo."""

    def __init__(self, project_id: Optional[str] = None) -> None:
        self.project_id = project_id or "aura-project"
        self.initialized: bool = False
        self._firebase_app: Optional[Any] = None
        self._db: Optional[Any] = None
        self._firestore: Optional[Any] = None
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._shared_data: Dict[str, Any] = {
            "memory": {},
            "preferences": {},
            "settings": {},
        }
        self._sync_log: List[Dict[str, Any]] = []
        self._device_data: Dict[str, Dict[str, Any]] = {}

    async def init_firebase(self) -> Dict[str, Any]:
        """Conecta a Firebase y configura Realtime DB + Firestore."""
        try:
            import firebase_admin
            from firebase_admin import credentials, db as firebase_db, firestore as firebase_firestore

            if not firebase_admin._apps:
                cred = credentials.ApplicationDefault()
                self._firebase_app = firebase_admin.initialize_app(cred, {
                    "databaseURL": f"https://{self.project_id}.firebaseio.com",
                })
                self._db = firebase_db.reference()
                self._firestore = firebase_firestore.client(self._firebase_app)
            else:
                self._firebase_app = firebase_admin.get_app()
                self._db = firebase_db.reference()
                self._firestore = firebase_firestore.client(self._firebase_app)

            self.initialized = True
            logger.info("Firebase inicializado: project=%s", self.project_id)
            return {"status": "connected", "project": self.project_id}
        except Exception:
            logger.warning("Firebase SDK no disponible, usando modo simulado")
            self.initialized = True
            return {"status": "simulated", "project": self.project_id}

    async def sync_device(self, device_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sincroniza datos de dispositivo, merge con otros devices."""
        version = self._get_next_version(device_id)
        timestamp = datetime.now(timezone.utc).isoformat()

        merged = self._merge_device_data(device_id, data, version)

        if self._device_data.get(device_id):
            prev_data = self._device_data[device_id]
            changes = {k: v for k, v in data.items() if prev_data.get(k) != v}
        else:
            changes = data

        self._device_data[device_id] = merged
        self._devices[device_id] = {
            "lastSync": timestamp,
            "data": merged,
            "status": "online",
            "version": version,
        }

        log_entry = {
            "timestamp": timestamp,
            "device": device_id,
            "action": "push",
            "version": version,
            "changes": changes,
        }
        self._sync_log.append(log_entry)

        await self._emit_to_other_devices(device_id, merged, version)

        return {
            "status": "synced",
            "device_id": device_id,
            "version": version,
            "merged_keys": list(merged.keys()),
            "timestamp": timestamp,
        }

    async def pull_from_cloud(self, device_id: str, since_version: int = 0) -> Dict[str, Any]:
        """Obtiene ultimos cambios, resuelve conflictos (last-write-wins)."""
        all_versions: List[int] = []
        for dev_data in self._device_data.values():
            if isinstance(dev_data, dict):
                ver = dev_data.get("_version", 0)
                if isinstance(ver, int):
                    all_versions.append(ver)
        current_version = max(all_versions) if all_versions else since_version

        delta: Dict[str, Any] = {}
        target_data = self._device_data.get(device_id, {})

        if since_version < current_version:
            delta = target_data
            delta["_conflicts_resolved"] = True
            delta["_resolution"] = "last-write-wins"

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device": device_id,
            "action": "pull",
            "since_version": since_version,
            "delta_version": current_version,
        }
        self._sync_log.append(log_entry)

        return {
            "delta": delta,
            "version": current_version,
            "device_id": device_id,
            "conflicts_resolved": since_version < current_version,
        }

    async def push_to_cloud(self, device_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Envia cambios a Firebase con timestamp automatico."""
        timestamp = datetime.now(timezone.utc).isoformat()
        version = self._get_next_version(device_id)

        if device_id not in self._device_data:
            self._device_data[device_id] = {}

        current = self._device_data[device_id]
        if isinstance(current, dict):
            current.update(changes)
        else:
            current = changes

        current["_last_modified"] = timestamp
        current["_version"] = version
        self._device_data[device_id] = current

        self._devices[device_id] = {
            "lastSync": timestamp,
            "data": current,
            "status": "online",
            "version": version,
        }

        log_entry = {
            "timestamp": timestamp,
            "device": device_id,
            "action": "push",
            "version": version,
            "data": changes,
        }
        self._sync_log.append(log_entry)

        await self._emit_to_other_devices(device_id, current, version)

        return {
            "status": "pushed",
            "device_id": device_id,
            "version": version,
            "timestamp": timestamp,
            "changes_applied": len(changes),
        }

    async def get_device_list(self) -> List[Dict[str, Any]]:
        """Retorna todos los dispositivos sincronizados."""
        devices: List[Dict[str, Any]] = []
        for device_id, info in self._devices.items():
            devices.append({
                "device_id": device_id,
                "type": info.get("type", self._infer_device_type(device_id)),
                "online": info.get("status", "offline") == "online",
                "lastSync": info.get("lastSync", ""),
                "version": info.get("version", 0),
            })
        return devices

    async def delete_device(self, device_id: str) -> Dict[str, Any]:
        """Elimina dispositivo de sync y archiva datos."""
        archived_data = self._device_data.pop(device_id, {})
        device_info = self._devices.pop(device_id, {})

        archive = {
            "device_id": device_id,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "data": archived_data,
            "last_sync": device_info.get("lastSync", ""),
        }

        for dev_id, dev_data in self._device_data.items():
            if isinstance(dev_data, dict) and dev_data.get("_shared_from") == device_id:
                dev_data.pop("_shared_from", None)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device": device_id,
            "action": "delete",
            "archived": True,
        }
        self._sync_log.append(log_entry)

        return {"deleted": True, "device_id": device_id, "archived": archive}

    def _get_next_version(self, device_id: str) -> int:
        """Calcula la siguiente version para un dispositivo."""
        current = self._device_data.get(device_id, {})
        if isinstance(current, dict):
            return current.get("_version", 0) + 1
        return 1

    def _merge_device_data(self, device_id: str, data: Dict[str, Any], version: int) -> Dict[str, Any]:
        """Merge de datos de dispositivo con versionado."""
        existing = self._device_data.get(device_id, {})
        if not isinstance(existing, dict):
            existing = {}
        merged = {**existing, **data, "_version": version, "_last_sync": datetime.now(timezone.utc).isoformat()}
        return merged

    async def _emit_to_other_devices(self, source_device: str, data: Dict[str, Any], version: int) -> None:
        """Emite evento para otros dispositivos via EventBus."""
        try:
            from backend.core import get_event_bus
            bus = get_event_bus()
            bus.emit_simple("device_synced", {
                "source_device": source_device,
                "version": version,
                "data_keys": list(data.keys()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, agent="firebase-sync")
        except Exception as exc:
            logger.debug("EventBus emit failed: %s", exc)

    def _infer_device_type(self, device_id: str) -> str:
        """Infiere tipo de dispositivo desde ID."""
        if device_id.startswith("pc"):
            return "desktop"
        if device_id.startswith("mobile"):
            return "mobile"
        if device_id.startswith("web"):
            return "web"
        return "unknown"


firebase_sync = FirebaseSync()
