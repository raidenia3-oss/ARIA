#!/usr/bin/env python3
"""
swarm_manager.py — Orquestador del enjambre multi-nodo.
Asigna proxies validos del pool a instancias de navegador (Infiltrator)
y maneja la rotación/reemplazo automático.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SwarmManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._instances: Dict[str, dict] = {}
        self._proxy_pool: List[dict] = []

    def load_proxy_pool(self, pool: List[dict]) -> None:
        with self._lock:
            self._proxy_pool = pool[:]
        logger.info(f"[Swarm] Pool cargado: {len(pool)} proxies")

    def acquire_proxy(self, instance_id: str) -> Optional[dict]:
        with self._lock:
            if not self._proxy_pool:
                return None
            proxy = random.choice(self._proxy_pool)
            self._instances[instance_id] = proxy
            logger.info(f"[Swarm] Instancia {instance_id} -> proxy {proxy.get('server')}")
            return proxy

    def release_proxy(self, instance_id: str) -> None:
        with self._lock:
            self._instances.pop(instance_id, None)

    def rotate_proxy(self, instance_id: str) -> Optional[dict]:
        with self._lock:
            if instance_id in self._instances:
                del self._instances[instance_id]
        return self.acquire_proxy(instance_id)


# Singleton global
swarm_manager = SwarmManager()
