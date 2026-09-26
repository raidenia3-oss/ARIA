# -*- coding: utf-8 -*-
"""AURA OS - AME Mobile Sync Receiver (SIMULADO, corre en AME/Flet)."""
from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime
from typing import Any, Dict, List

from backend.core import get_event_bus

LORA_AME_DIR = "data/lora_ame"
LORA_AME_PATH = os.path.join(LORA_AME_DIR, "lora_ame_latest.pth")


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class AMESyncReceiver:
    def __init__(self) -> None:
        self.event_bus = get_event_bus()
        self.last_received: str = ""
        self.training_active: bool = False
        os.makedirs(LORA_AME_DIR, exist_ok=True)

    async def receive_lora_from_pc(self) -> bool:
        """SIMULA recibir LoRA de PC (30MB) y verifica checksum."""
        try:
            await asyncio.sleep(2.0)
            os.makedirs(LORA_AME_DIR, exist_ok=True)
            with open(LORA_AME_PATH, "wb") as f:
                f.write(os.urandom(30 * 1024 * 1024))
            checksum = _md5(LORA_AME_PATH)
            self.last_received = datetime.now().isoformat()
            self.event_bus.emit_simple("ame_lora_received", {
                "size_mb": 30.0,
                "checksum": checksum,
                "timestamp": self.last_received,
            }, agent="ame_mobile")
            return True
        except Exception:
            return False

    async def train_ame_local(self) -> Dict[str, Any]:
        """SIMULA entrenamiento LoRA local en AME (10 min)."""
        self.training_active = True
        await asyncio.sleep(3.0)
        improvement = round(0.023 + 0.007, 4)
        self.training_active = False
        self.event_bus.emit_simple("ame_training_complete", {
            "improvement_percent": round(improvement * 100, 2),
            "new_adapter_path": LORA_AME_PATH,
            "timestamp": datetime.now().isoformat(),
        }, agent="ame_mobile")
        return {"improvement_percent": round(improvement * 100, 2), "new_adapter_path": LORA_AME_PATH}

    async def send_insights_to_pc(self) -> bool:
        """SIMULA envío de insights de AME a PC."""
        try:
            await asyncio.sleep(1.0)
            insights = [
                {"title": "Optimizacion de inference", "description": "Reducir batch size mejora latency 15%", "timestamp": datetime.now().isoformat()},
                {"title": "Patron de uso detectado", "description": "Mayor actividad 14:00-16:00 UTC", "timestamp": datetime.now().isoformat()},
                {"title": "Mejora de LoRA sugerida", "description": "Aumentar rank de 8 a 16", "timestamp": datetime.now().isoformat()},
            ]
            self.event_bus.emit_simple("ame_insights_sent", {
                "count": len(insights),
                "timestamp": datetime.now().isoformat(),
            }, agent="ame_mobile")
            return True
        except Exception:
            return False

    async def ame_sync_cycle(self) -> Dict[str, Any]:
        """Ciclo completo de sync: recibir, entrenar, enviar insights."""
        lora_ok = await self.receive_lora_from_pc()
        training = await self.train_ame_local()
        insights_ok = await self.send_insights_to_pc()
        self.event_bus.emit_simple("ame_sync_cycle_complete", {
            "lora_received": lora_ok,
            "training_improvement": training["improvement_percent"],
            "insights_sent": insights_ok,
            "timestamp": datetime.now().isoformat(),
        }, agent="ame_mobile")
        return {
            "lora_received": lora_ok,
            "training_improvement": training["improvement_percent"],
            "insights_sent": insights_ok,
            "timestamp": datetime.now().isoformat(),
        }


_ame_receiver: "AMESyncReceiver | None" = None


def get_ame_receiver() -> AMESyncReceiver:
    global _ame_receiver
    if _ame_receiver is None:
        _ame_receiver = AMESyncReceiver()
    return _ame_receiver