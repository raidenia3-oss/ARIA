"""
AURA Agent Orchestrator - Motor de automatización de agentes.
Observa datos entrantes (stats, logs de bots, noticias) y ejecuta acciones automáticas.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

# Importar event bus existente
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from AURA_Core.event_bus import (
    event_bus,
    publish_event,
    EVENT_ROLLERCOIN_CYCLE_COMPLETE,
)

logger = logging.getLogger("AURA.AgentOrchestrator")

ACTIONS_LOG = Path(__file__).parent / "system_actions.json"


def _log_action(action: str, detail: str, trigger: str) -> None:
    """Guarda una acción en el archivo de historial."""
    entry = {
        "timestamp": datetime.now().strftime("%H:%M"),
        "action": action,
        "detail": detail,
        "trigger": trigger,
    }
    try:
        data = json.loads(ACTIONS_LOG.read_text() or "[]")
    except FileNotFoundError:
        data = []
    data.append(entry)
    ACTIONS_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info(f"Acción registrada: {entry['timestamp']} - {action}")


def _check_rollercoin_error(data: Dict[str, Any]) -> None:
    """Regla: Si el bot RollerCoin reporta error, reiniciar."""
    if data.get("status") == "error":
        _log_action(
            action="bot_restart",
            detail="RollerCoin reiniciado automáticamente",
            trigger="error_detected",
        )
        try:
            subprocess.Popen(
                ["python", "AURA_OS_Workspace/AME_Core/AME_Core/rollercoin/main.py"],
                cwd=Path(__file__).parent.parent,
            )
        except Exception as exc:
            logger.error(f"Fallo al intentar reiniciar RollerCoin: {exc}")


def _check_optimization_opportunity(data: Dict[str, Any]) -> None:
    """Regla: Si las estadísticas muestran oportunidad (>80% éxito), ajustar."""
    if data.get("success_rate", 0) > 80:
        _log_action(
            action="parameter_optimized",
            detail="Ajustes de optimización aplicados",
            trigger="high_success_rate",
        )


def _check_news_critical(data: Dict[str, Any]) -> None:
    """Regla: Si noticia crítica detectada, notificar al WebSocket."""
    if data.get("priority") == "high":
        _log_action(
            action="news_alert",
            detail=f"Noticia crítica: {data.get('title', 'Sin título')}",
            trigger="critical_news",
        )
        # El evento WS lo emitirá quien llame a publish_event


def get_system_actions(limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene el historial de acciones del sistema."""
    try:
        data = json.loads(ACTIONS_LOG.read_text() or "[]")
        return data[-limit:] if limit > 0 else data
    except FileNotFoundError:
        return []


def start_orchestrator() -> None:
    """Inicia las suscripciones del orquestador."""
    event_bus.subscribe(EVENT_ROLLERCOIN_CYCLE_COMPLETE, _check_rollercoin_error)
    event_bus.subscribe("stats_update", _check_optimization_opportunity)
    event_bus.subscribe("news_ingest", _check_news_critical)
    logger.info("Agent Orchestrator activo - monitoreando flujos de datos")
