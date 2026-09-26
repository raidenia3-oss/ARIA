"""Self-healing system for automatic error recovery."""
from __future__ import annotations
import logging
from fastapi import APIRouter
from typing import Callable

logger = logging.getLogger("aria.resilience.healer")

router = APIRouter(prefix="/api/resilience", tags=["resilience"])

@router.get("/health")
async def health_check():
    return {"status": "ok", "healed": 0, "strategies": 0}


class SelfHealer:
    """Auto-recupera el sistema de errores comunes."""

    def __init__(self) -> None:
        self._strategies: dict[str, Callable] = {}
        self.router = None  # Compatibilidad con app.py (no usado pero requerido)

    def register_strategy(self, error_key: str, strategy: Callable) -> None:
        self._strategies[error_key] = strategy

    async def heal(self, error: Exception) -> bool:
        key = type(error).__name__
        strategy = self._strategies.get(key)
        if strategy:
            try:
                result = strategy(error)
                if hasattr(result, "__await__"):
                    await result
                logger.info(f"Healed error: {key}")
                return True
            except Exception as e:
                logger.error(f"Heal failed for {key}: {e}")
        return False

    def reset(self) -> None:
        """Reset the healer state"""
        self._strategies.clear()
