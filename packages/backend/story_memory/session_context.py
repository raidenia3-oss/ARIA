"""Session Context — mapeo de session_id a obra/personaje activo.

Permite que el chat existente mantenga compatibilidad: si una sesión tiene
contexto literario activo, el system prompt se enriquece automáticamente.

Almacenamiento: persistencia en disco mediante data/sessions.json.
- Carga inicial al primer uso (lazy).
- Guardado automático en cada mutación (set/clear).
- Formato JSON con lock de thread safety.
- No expone secretos: solo work_id + character_id + metadatos.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, Optional

_DEFAULT_STORE = os.path.join(
    os.environ.get("AURA_DATA_DIR", os.path.join(os.getcwd(), "data")),
    "sessions.json",
)

_lock = threading.Lock()
_session_contexts: Dict[str, Dict[str, Any]] = {}
_store_path: str = _DEFAULT_STORE
_loaded: bool = False


def _ensure_loaded() -> None:
    """Carga inicial de sesiones desde disco (lazy, thread-safe)."""
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        try:
            if os.path.isfile(_store_path):
                with open(_store_path, "r", encoding="utf-8") as f:
                    _session_contexts.update(json.load(f))
        except (OSError, json.JSONDecodeError, ValueError):
            _session_contexts.clear()
        _loaded = True


def _persist() -> None:
    """Guarda las sesiones en disco (no expone secretos)."""
    try:
        os.makedirs(os.path.dirname(_store_path), exist_ok=True)
        tmp = _store_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_session_contexts, f, indent=2)
        os.replace(tmp, _store_path)
    except OSError:
        pass


def set_session_context(
    session_id: str,
    work_id: str,
    character_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Asocia una sesión de chat con un contexto literario (obra + personaje)."""
    _ensure_loaded()
    with _lock:
        _session_contexts[session_id] = {
            "work_id": work_id,
            "character_id": character_id,
            "extra": extra or {},
            "active": True,
        }
        ctx = dict(_session_contexts[session_id])
        _persist()
        _broadcast_session_change(work_id, session_id, "active")
    return ctx


def get_session_context(session_id: str) -> Optional[Dict[str, Any]]:
    """Recupera el contexto literario para una sesión."""
    _ensure_loaded()
    with _lock:
        return dict(_session_contexts.get(session_id, None)) if _session_contexts.get(session_id) else None


def clear_session_context(session_id: str) -> Dict[str, Any]:
    """Desvincula una sesión del contexto literario."""
    _ensure_loaded()
    with _lock:
        removed = _session_contexts.pop(session_id, None)
        _persist()
        if removed:
            _broadcast_session_change(removed.get("work_id", "unknown"), session_id, "cleared")
            return {"cleared": True, "was_active": True}
        return {"cleared": False}


def clear_all() -> int:
    """Limpia todos los mapeos de sesión (para testing)."""
    _ensure_loaded()
    with _lock:
        count = len(_session_contexts)
        _session_contexts.clear()
        _persist()
        return count


def set_store_path(path: str) -> None:
    """Override de la ruta de persistencia (para testing)."""
    global _store_path, _loaded, _session_contexts
    with _lock:
        _store_path = path
        _session_contexts.clear()
        _loaded = False


def get_store_path() -> str:
    """Retorna la ruta de persistencia actual (para testing)."""
    return _store_path


def _broadcast_session_change(work_id: str, session_id: str, status: str) -> None:
    """Transmite un cambio de sesión a AME suscritos (no bloqueante)."""
    try:
        import asyncio
        asyncio.get_running_loop()
        from backend.websocket_manager import ws_gateway
        asyncio.ensure_future(ws_gateway.broadcast(
            "session_change",
            {"work_id": work_id, "session_id": session_id, "status": status},
            work_id=work_id,
        ))
    except Exception:
        pass
