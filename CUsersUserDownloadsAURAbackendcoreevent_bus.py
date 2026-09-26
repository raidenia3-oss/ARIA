from typing import List, Optional, Callable
from threading import Thread, Lock
from loguru import logger
from backend.models.event import CoreEvent, EventType


class EventBus:
    """Sistema de eventos para manejar la comunicación entre componentes."""
    
    def __init__(self):
        self._queue: Queue = Queue()
        self._listeners: dict[str, List[Callable]] = {}
        self._lock = Lock()
        self._running = False
        self._thread: Optional[Thread] = None
    
    def start(self) -> None:
        """Inicia el hilo del EventBus."""
        if not self._running:
            self._running = True
            self._thread = Thread(target=self._process_events, daemon=True)
            self._thread.start()
    
    def stop(self) -> None:
        """Detiene el hilo del EventBus."""
        self._running = False
        if self._thread:
            self._thread.join()
    
    def emit(self, event: CoreEvent) -> None:
        """Emitir un evento al bus."""
        self._queue.put(event)
        self._notify_listeners(event)
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Suscribirse a un tipo de evento."""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
    
    def _notify_listeners(self, event: CoreEvent) -> None:
        """Notificar a los listeners registrados."""
        with self._lock:
            if event.type in self._listeners:
                for callback in self._listeners[event.type]:
                    callback(event)
    
    def _process_events(self) -> None:
        """Procesar eventos en el hilo del EventBus."""
        while self._running:
            try:
                event = self._queue.get(timeout=0.1)
                logger.debug(f"EventBus: Procesando evento {event.type}")
                self._notify_listeners(event)
            except:
                continue
