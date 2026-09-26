#!/usr/bin/env python3
"""
proxy_manager.py — Gestor de rotación de proxies para AURA Swarm.
Implementa un algoritmo Round-Robin para distribuir las peticiones entre
una lista de proxies configurada en el entorno.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Gestiona una lista de proxies y rota la selección para evitar el baneo.
    Formato esperado de PROXY_LIST: "ip:port:user:pass,ip:port:user:pass"
    """
    def __init__(self) -> None:
        self._proxies: List[Dict[str, str]] = []
        self._current_index: int = 0
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Carga la lista de proxies desde la variable de entorno PROXY_LIST."""
        proxy_string = os.environ.get("PROXY_LIST", "").strip()
        if not proxy_string:
            logger.warning("PROXY_LIST no configurada. El sistema operará sin proxies.")
            return

        raw_list = proxy_string.split(",")
        for item in raw_list:
            parts = item.strip().split(":")
            if len(parts) == 4:
                self._proxies.append({
                    "server": f"http://{parts[0]}:{parts[1]}",
                    "username": parts[2],
                    "password": parts[3],
                })
            elif len(parts) == 2:
                self._proxies.append({
                    "server": f"http://{parts[0]}:{parts[1]}",
                    "username": None,
                    "password": None,
                })
            else:
                logger.error(f"Formato de proxy inválido omitido: {item}")

        logger.info(f"ProxyManager: {len(self._proxies)} proxies cargados correctamente.")

    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Retorna el siguiente proxy en la lista (Round-Robin)."""
        if not self._proxies:
            return None
        
        proxy = self._proxies[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._proxies)
        return proxy

    def refresh_proxies(self) -> None:
        """Permite recargar la lista de proxies sin reiniciar el proceso."""
        self._load_proxies()

# Singleton para uso global en el backend
proxy_manager = ProxyManager()
