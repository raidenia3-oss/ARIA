"""Cuota diaria para el proveedor Gemini CLI.

Contador LOCAL por dia (measured) + limite configurable con source="documented".
Nunca estima "restante": solo dice si puede llamar o si esta en cooldown.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class QuotaConfig:
    """Limite documentado configurable.

    max_calls_per_day: <=0 desactiva la cuota (ilimitado). Fuente: documented.
    cooldown_seconds: tiempo de bloqueo despues de agotar la cuota.
    """
    max_calls_per_day: int = 0  # 0 = sin limite (configurable via env)
    cooldown_seconds: float = 60.0
    source: str = "documented"

    @property
    def enabled(self) -> bool:
        return self.max_calls_per_day > 0


@dataclass
class DailyCounter:
    """Contador local por dia. Reset automatico al cambiar el dia (UTC)."""
    day: str  # YYYY-MM-DD UTC
    calls: int = 0
    last_reset: float = 0.0


class QuotaManager:
    """Gestiona la cuota diaria y el cooldown para un proveedor.

    Thread-safe (un Lock). No estima cuota restante: solo reporta measured.
    """

    def __init__(
        self,
        state_path: str,
        config: Optional[QuotaConfig] = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.config = config or QuotaConfig(
            max_calls_per_day=int(os.environ.get("AURA_GEMINI_CLI_DAILY_LIMIT", "0")),
            cooldown_seconds=float(os.environ.get("AURA_GEMINI_CLI_COOLDOWN", "60")),
        )
        self._lock = threading.Lock()
        self._counter: Optional[DailyCounter] = None
        self._cooldown_until: float = 0.0
        self._load()

    # --- persistencia ---

    def _load(self) -> None:
        if not self.state_path.exists():
            self._counter = DailyCounter(day=self._today(), calls=0)
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._counter = DailyCounter(
                day=data.get("day", self._today()),
                calls=int(data.get("calls", 0)),
                last_reset=float(data.get("last_reset", 0.0)),
            )
            self._cooldown_until = float(data.get("cooldown_until", 0.0))
        except Exception:
            self._counter = DailyCounter(day=self._today(), calls=0)
            self._cooldown_until = 0.0

    def _save(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "day": self._counter.day if self._counter else self._today(),
                "calls": self._counter.calls if self._counter else 0,
                "last_reset": self._counter.last_reset if self._counter else 0.0,
                "cooldown_until": self._cooldown_until,
            }
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # --- helpers ---

    @staticmethod
    def _today() -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _ensure_counter(self) -> DailyCounter:
        if self._counter is None:
            self._counter = DailyCounter(day=self._today(), calls=0)
        if self._counter.day != self._today():
            # Nuevo dia: reseteo automatico del measured counter.
            self._counter = DailyCounter(day=self._today(), calls=0)
        return self._counter

    # --- API publica ---

    def can_call(self) -> Tuple[bool, Optional[str]]:
        """Devuelve (puede_llamar, motivo_si_no).

        Nunca estima "restante". Solo dice si la cuota permite la llamada
        o si el proveedor esta en cooldown.
        """
        if not self.config.enabled:
            return True, None  # sin limite configurado

        now = time.time()
        if now < self._cooldown_until:
            remaining = int(self._cooldown_until - now)
            return False, f"provider in cooldown for {remaining}s (quota exhausted)"

        counter = self._ensure_counter()
        if counter.calls >= self.config.max_calls_per_day:
            self._cooldown_until = now + self.config.cooldown_seconds
            self._save()
            return False, (
                f"daily quota exhausted: {counter.calls} calls measured "
                f"(limit={self.config.max_calls_per_day}, source={self.config.source})"
            )
        return True, None

    def record_call(self, success: bool) -> None:
        """Incrementa el measured counter. Llamada tras cada intento real."""
        with self._lock:
            counter = self._ensure_counter()
            counter.calls += 1
            counter.last_reset = time.time()
            self._save()

    def state(self) -> Dict:
        """Snapshot observable para audit (solo measured, nunca estimado)."""
        with self._lock:
            counter = self._ensure_counter()
            now = time.time()
            in_cooldown = now < self._cooldown_until
            return {
                "day": counter.day,
                "calls_measured": counter.calls,
                "limit": self.config.max_calls_per_day,
                "source": self.config.source,
                "enabled": self.config.enabled,
                "in_cooldown": in_cooldown,
                "cooldown_remaining_s": max(0, int(self._cooldown_until - now)) if in_cooldown else 0,
            }


# --- singleton ---

_quota_instance: Optional[QuotaManager] = None


def get_quota_manager(state_path: Optional[str] = None) -> QuotaManager:
    global _quota_instance
    if _quota_instance is None:
        default_path = os.environ.get(
            "AURA_GEMINI_CLI_QUOTA_STATE",
            str(Path.home() / ".aura" / "gemini_cli_quota.json"),
        )
        _quota_instance = QuotaManager(state_path or default_path)
    return _quota_instance


def reset_quota_manager() -> None:
    global _quota_instance
    _quota_instance = None