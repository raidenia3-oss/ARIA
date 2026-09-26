"""Automatic patch application system."""
from __future__ import annotations
import logging
from fastapi import APIRouter

logger = logging.getLogger("aria.evolution.patcher")

router = APIRouter(prefix="/api/evolution", tags=["evolution"])

@router.get("/status")
async def patcher_status():
    return {"status": "ok", "patches": 0, "applied": 0}


class Patcher:
    """Aplica patches automáticos al sistema."""

    def __init__(self) -> None:
        self._patches: list[dict] = []
        self.router = None  # Compatibilidad con app.py

    def register(self, patch_id: str, description: str, apply_fn) -> None:
        self._patches.append({"id": patch_id, "desc": description, "fn": apply_fn})

    async def apply_patch(self, patch_id: str) -> bool:
        for p in self._patches:
            if p["id"] == patch_id:
                try:
                    result = p["fn"]()
                    if hasattr(result, "__await__"):
                        await result
                    logger.info(f"Patch '{patch_id}' applied")
                    return True
                except Exception as e:
                    logger.error(f"Patch '{patch_id}' failed: {e}")
        return False

    async def apply_all(self) -> int:
        applied = 0
        for p in self._patches:
            if await self.apply_patch(p["id"]):
                applied += 1
        return applied
