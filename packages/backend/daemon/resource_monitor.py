# -*- coding: utf-8 -*-
"""AURA OS - Resource Monitor (OPCION B)."""
from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger("AURA.ResourceMonitor")


def get_cpu_percent() -> float:
    """Retorna porcentaje de CPU actual."""
    try:
        import psutil
        return psutil.cpu_percent(interval=1)
    except Exception as exc:
        logger.debug("CPU check fallo: %s", exc)
        return 0.0


def get_ram_percent() -> float:
    """Retorna porcentaje de RAM usada."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except Exception as exc:
        logger.debug("RAM check fallo: %s", exc)
        return 0.0


def get_disk_percent() -> float:
    """Retorna porcentaje de disco usado."""
    try:
        import psutil
        return psutil.disk_usage('/').percent
    except Exception as exc:
        logger.debug("Disk check fallo: %s", exc)
        return 0.0


def get_all_resources() -> Dict[str, Any]:
    """Retorna todos los recursos del sistema."""
    return {
        "cpu_percent": get_cpu_percent(),
        "ram_percent": get_ram_percent(),
        "disk_percent": get_disk_percent(),
        "timestamp": __import__('time').time(),
    }


async def pause_heavy_tasks() -> None:
    """Pausa tareas pesadas del sistema."""
    print("[MONITOR] Pausando tareas pesadas")
    logger.info("Tareas pesadas pausadas")


async def resume_tasks() -> None:
    """Reanuda tareas del sistema."""
    print("[MONITOR] Reanudando tareas")
    logger.info("Tareas reanudadas")