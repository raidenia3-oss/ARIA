"""Reverse-engineer (REA) autonomous service module.

Exporta el launcher autónomo y el bridge para navegación web, análisis
de videos de YouTube y fusión de mods/juegos.
"""
from backend.reverse_engineer.launcher import (
    start_reverse_engineer,
    get_service_status,
    _SERVICE_NAME,
)
from backend.reverse_engineer.rea_bridge import REABridge, get_rea_bridge

__all__ = [
    "start_reverse_engineer",
    "get_service_status",
    "_SERVICE_NAME",
    "REABridge",
    "get_rea_bridge",
]
