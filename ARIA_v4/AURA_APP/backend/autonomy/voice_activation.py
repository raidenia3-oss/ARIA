"""Voice Activation — Activación por voz sin comandos.

Escucha palabras de activación (wake word) para activar ARIA
sin necesidad de escribir nada.
"""

import asyncio
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable


class VoiceActivation:
    """Escucha wake-word para activación manos libres."""

    WAKE_WORDS: List[str] = [
        "prendete", "despierta", "hola aria", "oye aria",
        "enciende", "ok aria", "hey aria",
    ]

    def __init__(self, on_activate: Optional[Callable] = None):
        self.on_activate = on_activate
        self.listening = False
        self.active = False
        self.last_wake_time: Optional[datetime] = None
        self.wake_count = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sensitivity = 0.7
        self._voice_engine = None
        self._stt_engine = None
        self._cooldown_seconds = 3

    async def start(self):
        """Inicia escucha de voz en background."""
        self.active = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[VoiceActivation] Escucha activada — di 'Prendete' o 'Despierta'")

    async def stop(self):
        """Detiene escucha de voz."""
        self.active = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        print("[VoiceActivation] Escucha detenida")

    def _listen_loop(self):
        """Loop principal de escucha."""
        while self.active:
            try:
                if self._check_wake_word():
                    self._handle_wake_detected()
                time.sleep(0.5)
            except Exception as e:
                print(f"[VoiceActivation] Listen error: {e}")
                time.sleep(2)

    def _check_wake_word(self) -> bool:
        """Verifica si se detectó wake word."""
        try:
            audio_text = self._capture_audio_text()
            if audio_text:
                return self._match_wake_word(audio_text)
        except Exception:
            pass
        return False

    def _capture_audio_text(self) -> Optional[str]:
        """Captura audio y lo convierte a texto."""
        try:
            mic_input = os.environ.get('ARIA_VOICE_INPUT', '')
            if mic_input and len(mic_input.strip()) > 0:
                text = mic_input.strip()
                os.environ['ARIA_VOICE_INPUT'] = ''
                return text
        except Exception:
            pass
        return None

    def _match_wake_word(self, text: str) -> bool:
        """Coincide wake word en texto."""
        text_lower = text.lower().strip()
        for wake_word in self.WAKE_WORDS:
            if wake_word in text_lower:
                return True
        return False

    def _handle_wake_detected(self):
        """Maneja detección de wake word."""
        now = datetime.now()
        if self.last_wake_time:
            cooldown = (now - self.last_wake_time).total_seconds()
            if cooldown < self._cooldown_seconds:
                return

        self.last_wake_time = now
        self.wake_count += 1
        print(f"[VoiceActivation] Wake word detectado ({self.wake_count})")

        if self.on_activate:
            try:
                self.on_activate()
            except Exception as e:
                print(f"[VoiceActivation] Activation error: {e}")

    def set_sensitivity(self, level: float):
        """Ajusta sensibilidad de detección."""
        self._sensitivity = max(0.0, min(1.0, level))

    def get_status(self) -> Dict:
        """Obtiene estado de activación por voz."""
        return {
            'active': self.active,
            'listening': self.listening,
            'wake_count': self.wake_count,
            'last_wake': self.last_wake_time.isoformat() if self.last_wake_time else None,
            'sensitivity': self._sensitivity,
            'cooldown_seconds': self._cooldown_seconds,
        }


class VoiceCommandParser:
    """Parsea comandos de voz en intenciones."""

    INTENT_MAP = {
        'prendete': 'activate',
        'despierta': 'activate',
        'enciende': 'activate',
        'hola': 'greet',
        'buenos': 'greet',
        'qué hora': 'query',
        'hora': 'query',
        'qué tiempo': 'query',
        'tiempo': 'query',
        'clima': 'query',
        'busca': 'search',
        'buscar': 'search',
        'abre': 'open',
        'abrir': 'open',
        'usb': 'usb',
        'expande': 'expand',
        'maximiza': 'maximize',
        'aprende': 'learn',
        'memoriza': 'learn',
        'recuerda': 'learn',
        'para': 'stop',
        'detente': 'stop',
        'reproduce': 'play',
        'musica': 'play',
        'música': 'play',
    }

    @classmethod
    def parse(cls, text: str) -> Dict[str, Any]:
        """Parsea texto de voz en intención."""
        text_lower = text.lower().strip()

        for phrase, intent in cls.INTENT_MAP.items():
            if phrase in text_lower:
                return {
                    'intent': intent,
                    'confidence': 0.90,
                    'raw_text': text,
                    'parsed': phrase,
                }

        return {
            'intent': 'conversation',
            'confidence': 0.50,
            'raw_text': text,
            'parsed': None,
        }
