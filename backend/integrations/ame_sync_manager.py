# -*- coding: utf-8 -*-
"""AURA OS - AME Sync Manager: PC <-> Mobile LoRA sync (SIMULADO)."""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core import get_event_bus

LORA_DIR = "data/lora_adapters"
SYNC_LOG: List[Dict[str, Any]] = []
LORA_VERSION = 0


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class AMESyncManager:
    def __init__(self, ame_device_id: str = "ame_primary") -> None:
        self.ame_device_id = ame_device_id
        self.last_sync: Optional[str] = None
        self.lora_version: int = 0
        self.event_bus = get_event_bus()
        self.sync_log: List[Dict[str, Any]] = []
        os.makedirs(LORA_DIR, exist_ok=True)

    async def prepare_lora_for_sync(self) -> Dict[str, Any]:
        lora_path = os.path.join(LORA_DIR, f"lora_adapter_v{self.lora_version}.pth")
        if not os.path.exists(lora_path):
            with open(lora_path, "wb") as f:
                f.write(os.urandom(30 * 1024 * 1024))
        size_mb = os.path.getsize(lora_path) / (1024 * 1024)
        checksum = _md5(lora_path)
        if size_mb > 50:
            zip_path = lora_path + ".zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(lora_path, os.path.basename(lora_path))
            return {"lora_path": zip_path, "size_mb": round(os.path.getsize(zip_path) / (1024 * 1024), 2), "checksum": _md5(zip_path), "compressed": True}
        return {"lora_path": lora_path, "size_mb": round(size_mb, 2), "checksum": checksum, "compressed": False}

    async def send_lora_to_ame(self, ame_device_id: str = None) -> Dict[str, Any]:
        device = ame_device_id or self.ame_device_id
        info = await self.prepare_lora_for_sync()
        await asyncio.sleep(1.5)
        self.event_bus.emit_simple("ame_lora_sent", {"size_mb": info["size_mb"], "checksum": info["checksum"], "timestamp": datetime.now().isoformat(), "device": device}, agent="ame_sync")
        await asyncio.sleep(0.5)
        improvement = round(0.023 + (info["size_mb"] * 0.0003), 4)
        return {"success": True, "ame_improvement": improvement, "size_mb": info["size_mb"], "checksum": info["checksum"], "timestamp": datetime.now().isoformat()}

    async def receive_ame_insights(self) -> List[Dict[str, Any]]:
        await asyncio.sleep(1.0)
        insights = [
            {"title": "Optimizacion de inference", "description": "AME detectó que reducir batch size mejora latency 15%", "timestamp": datetime.now().isoformat()},
            {"title": "Patron de uso detectado", "description": "Mayor actividad en horario 14:00-16:00 UTC", "timestamp": datetime.now().isoformat()},
            {"title": "Mejora de LoRA sugerida", "description": "Aumentar rank de 8 a 16 para mejor precision", "timestamp": datetime.now().isoformat()},
        ]
        self.event_bus.emit_simple("ame_insights_received", {"count": len(insights), "timestamp": datetime.now().isoformat()}, agent="ame_sync")
        return insights

    async def sync_bidirectional(self) -> Dict[str, Any]:
        lora_result = await self.send_lora_to_ame()
        insights = await self.receive_ame_insights()
        self.last_sync = datetime.now().isoformat()
        self.lora_version += 1
        self.sync_log.append({"timestamp": self.last_sync, "lora_sent_mb": lora_result["size_mb"], "insights_received": len(insights), "lora_version": self.lora_version})
        self.event_bus.emit_simple("ame_sync_cycle_complete", {"lora_sent_mb": lora_result["size_mb"], "insights_received": len(insights), "timestamp": self.last_sync, "lora_version": self.lora_version}, agent="ame_sync")
        return {"lora_sent_mb": lora_result["size_mb"], "insights_received": len(insights), "timestamp": self.last_sync, "lora_version": self.lora_version}


_ame_sync: Optional[AMESyncManager] = None


def get_ame_sync() -> AMESyncManager:
    global _ame_sync
    if _ame_sync is None:
        _ame_sync = AMESyncManager()
    return _ame_sync