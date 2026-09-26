"""
FASE 21 - AURA Emote Engine
============================
Motor de Estados Visuales y Animación de Avatar.

- FSM con estados: IDLE, THINKING, SPEAKING, READING, FAILURE.
- Emite eventos WS a ws://localhost:8765 con contrato JSON:
    {"type": "avatar_state_change", "state": "<ESTADO>"}
- Pensado para acoplarse a EventManager y a módulos centrales.
"""

from __future__ import annotations

import json
import logging
import time
import winsound
from enum import Enum
from typing import Optional

logger = logging.getLogger("EmoteEngine")
logger.setLevel(logging.DEBUG)


class AvatarState(str, Enum):
    """Estados canónicos del avatar/hud."""

    IDLE = "IDLE"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    READING = "READING"
    FAILURE = "FAILURE"


class EmoteEngine:
    """
    FSM de estado visual + dispatcher WS.

    Uso básico:
        engine = EmoteEngine(ws_send_callback=mi_funcion_ws)
        engine.set_state(AvatarState.THINKING)
    """

    def __init__(self, ws_send_callback=None):
        self._state: AvatarState = AvatarState.IDLE
        self._ws_send = ws_send_callback  # callable(str) -> None
        self._last_change: float = 0.0

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def set_state(self, new_state: AvatarState) -> None:
        """Cambia el estado y emite evento WS inmediatamente."""
        if not isinstance(new_state, AvatarState):
            try:
                new_state = AvatarState(str(new_state))
            except Exception:
                logger.error("Estado de avatar inválido: %r", new_state)
                return

        if new_state == self._state:
            logger.debug("Estado %s repetido; se ignora.", new_state.value)
            return

        old_state = self._state
        self._state = new_state
        self._last_change = time.time()
        logger.info("Avatar: %s -> %s", old_state.value, new_state.value)

        event = {
            "type": "avatar_state_change",
            "state": new_state.value,
            "ts": self._last_change,
        }
        self._dispatch(event)

        # Alerta sonora sutil en transiciones relevantes
        if new_state in (AvatarState.SPEAKING, AvatarState.FAILURE):
            self._play_beep()

    def current_state(self) -> AvatarState:
        return self._state

    def attach_ws(self, ws_send_callback) -> None:
        """Inyecta dependencia de envío WS (para integración con EventManager/Chronos)."""
        self._ws_send = ws_send_callback

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _dispatch(self, payload: dict) -> None:
        """Envía el evento por WebSocket si hay callback registrado."""
        try:
            if self._ws_send is None:
                logger.debug("WS no conectado; evento cacheado: %s", payload)
                return
            self._ws_send(json.dumps(payload))
        except Exception as e:
            logger.error("Error despachando evento WS: %s", e)

    @staticmethod
    def _play_beep() -> None:
        try:
            winsound.Beep(1200, 100)
        except Exception:
            pass


# ------------------------------------------------------------------
# Atajos de integración por módulo (para importar desde AURA_Core)
# ------------------------------------------------------------------
_emote_engine: Optional[EmoteEngine] = None


def get_emote_engine() -> EmoteEngine:
    global _emote_engine
    if _emote_engine is None:
        _emote_engine = EmoteEngine()
    return _emote_engine


def set_state(state: AvatarState) -> None:
    get_emote_engine().set_state(state)


# ------------------------------------------------------------------
# Self-test rápido
# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def fake_ws(msg: str):
        print(">> WS:", msg)

    engine = EmoteEngine(ws_send_callback=fake_ws)
    engine.set_state(AvatarState.THINKING)
    engine.set_state(AvatarState.READING)
    engine.set_state(AvatarState.SPEAKING)
    engine.set_state(AvatarState.FAILURE)
    engine.set_state(AvatarState.IDLE)
