"""Mobile story context routes — sincronización literaria para clientes AME.

Expone una pasarela móvil sobre el mapeo de sesiones literarias de
`backend.story_memory.session_context`, permitiendo que el cliente móvil
consulte y actualice la obra/personaje activos de su sesión en tiempo real.

Contratos (REST, retrocompatibles con /api/chat):
- GET    /api/mobile/story/context/{session_id}  → obra/personaje activos (o vacío)
- POST   /api/mobile/story/context/{session_id}  → vincular obra+personaje
- DELETE /api/mobile/story/context/{session_id}  → desvincular la sesión
- GET    /api/mobile/story                       → resumen de estado literario

No expone secretos. Reutiliza `session_context` y `StoryContextManager`
manteniendo intactos los contratos WebSocket/REST existentes del chat.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.story_memory.session_context import (
    clear_session_context,
    get_session_context,
    set_session_context,
)
from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible

_story_storage = StoryStorage()
_character_bible = CharacterBible()

router = APIRouter(prefix="/api/mobile/story", tags=["mobile_story"])


def _public_context(ctx: Dict[str, Any] | None) -> Dict[str, Any]:
    """Devuelve solo campos no sensibles del contexto literal."""
    if not ctx:
        return {"active": False, "work_id": None, "character_id": None}
    return {
        "active": bool(ctx.get("active", True)),
        "work_id": ctx.get("work_id"),
        "character_id": ctx.get("character_id"),
    }


@router.get("/context/{session_id}")
async def get_mobile_story_context(session_id: str) -> Dict[str, Any]:
    """Obtiene la obra y personaje activos de una sesión móvil (o vacío)."""
    ctx = get_session_context(session_id)
    if not ctx:
        return {"session_id": session_id, "active": False, "work_id": None, "character_id": None}

    work_id = ctx.get("work_id")
    character_id = ctx.get("character_id")

    work_title: Any = None
    character_name: Any = None
    if work_id:
        work = _story_storage.get_work(str(work_id))
        if work:
            work_title = work.get("title")
    if work_id and character_id:
        char = _character_bible.get(str(work_id), str(character_id))
        if char:
            character_name = char.get("name")

    return {
        "session_id": session_id,
        "active": True,
        "work_id": work_id,
        "character_id": character_id,
        **({"work_title": work_title} if work_title else {}),
        **({"character_name": character_name} if character_name else {}),
    }


@router.post("/context/{session_id}")
async def set_mobile_story_context(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Vincula una sesión móvil con una obra y un personaje."""
    work_id = str(payload.get("work_id", "")).strip()
    character_id = str(payload.get("character_id", "")).strip()
    if not work_id or not character_id:
        raise HTTPException(
            status_code=422,
            detail="work_id and character_id are required",
        )
    ctx = set_session_context(session_id, work_id, character_id, payload.get("extra"))
    return {
        "session_id": session_id,
        "status": "bound",
        "context": _public_context(ctx),
    }


@router.delete("/context/{session_id}")
async def clear_mobile_story_context(session_id: str) -> Dict[str, Any]:
    """Desvincula la sesión móvil del contexto literario."""
    return {"session_id": session_id, **clear_session_context(session_id)}


@router.get("")
async def mobile_story_summary() -> Dict[str, Any]:
    """Resumen del estado de sincronización literaria para clientes móviles."""
    return {
        "status": "ok",
        "endpoints": [
            "GET/POST/DELETE /api/mobile/story/context/{session_id}",
        ],
        "note": "El chat móvil mantiene el contrato /api/chat con session_id; "
                "el contexto literario se inyecta en el system prompt.",
    }