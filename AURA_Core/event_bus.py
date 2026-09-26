"""
AURA Event Bus - Sistema de comunicación entre módulos basado en eventos.
Permite a los módulos publicar y suscribirse a eventos para una comunicación asíncrona.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Any
from threading import Lock
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AURA.EventBus")


class EventBus:
    """Clase principal del sistema de eventos."""

    def __init__(self):
        self._events: Dict[str, List[Callable]] = {}
        self._lock = Lock()
        self._event_history: List[Dict[str, Any]] = []
        self._history_file = Path(__file__).parent / "event_history.json"

    def publish(self, event_name: str, data: Any = None) -> None:
        """Publica un evento y notifica a todos los suscriptores."""
        with self._lock:
            if event_name not in self._events:
                return

            # Registrar el evento en el historial
            event_data = {
                "timestamp": datetime.now().isoformat(),
                "event_name": event_name,
                "data": data,
            }
            self._event_history.append(event_data)
            self._save_history()

            # Notificar a los suscriptores
            for callback in self._events[event_name]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(
                        f"Error al ejecutar callback para evento {event_name}: {str(e)}"
                    )

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """Suscribe una función a un evento específico."""
        with self._lock:
            if event_name not in self._events:
                self._events[event_name] = []
            self._events[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> None:
        """Desuscribe una función de un evento específico."""
        with self._lock:
            if event_name in self._events:
                try:
                    self._events[event_name].remove(callback)
                except ValueError:
                    pass

    def _save_history(self) -> None:
        """Guarda el historial de eventos en un archivo."""
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_file, "w", encoding="utf-8") as f:
                json.dump(self._event_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar historial de eventos: {str(e)}")

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene el historial de eventos."""
        return self._event_history[-limit:] if limit > 0 else self._event_history.copy()


# Instancia global del EventBus
event_bus = EventBus()

# Eventos definidos
EVENT_ROLLERCOIN_CYCLE_COMPLETE = "rollercoin_cycle_complete"
EVENT_SOCIAL_POST_READY = "social_post_ready"
EVENT_VIDEO_CONTENT_READY = "video_content_ready"


# Función de utilidad para publicar eventos desde cualquier módulo
def publish_event(event_name: str, data: Any = None) -> None:
    """Publica un evento usando el EventBus global."""
    event_bus.publish(event_name, data)


# Función de utilidad para suscribirse a eventos
def subscribe_event(event_name: str, callback: Callable) -> None:
    """Suscribe una función a un evento usando el EventBus global."""
    event_bus.subscribe(event_name, callback)


# Función de utilidad para obtener el historial de eventos
def get_event_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene el historial de eventos usando el EventBus global."""
    return event_bus.get_history(limit)
