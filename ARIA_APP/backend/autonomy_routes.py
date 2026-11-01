"""Las rutas de autonomía de ARIA para el backend de v4 (FastAPI).

ARIA tiene un solo cerebro y vive **en su propio proceso**. Estas rutas no
son un proxy de otro servicio: son una ventana al runtime local
(`ARIA_APP.autonomy`), el mismo que mueve el escritorio de PyQt5.

Por eso este módulo no decide nada: le pasa la llamada al runtime y
devuelve su respuesta tal cual. No hay puertos, ni clientes HTTP, ni un
núcleo en otra máquina: quien pregunta, pregunta en proceso.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

ARIA_APP = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = ARIA_APP.parent
for _sys_path in (str(_PROJECT_ROOT), str(ARIA_APP)):
    if _sys_path not in sys.path:
        sys.path.insert(0, _sys_path)

from ARIA_APP.autonomy.runtime import SERVER, get_runtime  # noqa: E402

log = logging.getLogger(__name__)

router = APIRouter()


#: Ingestas en vuelo.
#:
#: Sin esta referencia el recolector de basura puede cancelar una ingesta a
#: medio camino, y ARIA se quedaría sin enterarse de medio mundo.
_INGEST_TASKS: set = set()


async def ingest_into_runtime(
    kind: str,
    text: str,
    source: str = "escritorio",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Informa al runtime de lo que pasa, sin bloquear a quien pregunta.

    El runtime es local y escribe en disco, así que la llamada va en un hilo
    aparte: la respuesta del chat no puede esperar a que termine de escribir.
    """
    if not text or not text.strip():
        return
    body = payload or {}
    task = asyncio.create_task(
        asyncio.to_thread(get_runtime().ingest, kind, text, source, body)
    )
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)


def _body(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """El cuerpo de la petición, o un dict vacío si no viene."""
    return payload if isinstance(payload, dict) else {}


def _runtime():
    return get_runtime()


# ── El estado del runtime ─────────────────────────────────────────────


@router.get("/api/autonomy/status")
async def autonomy_status() -> Dict[str, Any]:
    """Pulso, presencia, agenda, lecciones y episodios de ARIA."""
    return _runtime().status()


@router.post("/api/autonomy/mode")
async def autonomy_mode(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Cambia el modo: activa, tranquila o dormida."""
    return _runtime().set_mode(str(_body(payload).get("mode", "activa")))


@router.post("/api/autonomy/toggle")
async def autonomy_toggle(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Enciende o apaga la capacidad de actuar sola."""
    body = _body(payload)
    enabled = body.get("enabled")
    return _runtime().toggle(None if enabled is None else bool(enabled))


@router.get("/api/autonomy/presence")
async def autonomy_presence() -> Dict[str, Any]:
    """Dónde está ARIA y qué cara pone."""
    return _runtime().presence()


@router.post("/api/autonomy/presence")
async def autonomy_set_presence(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Cambia dónde está ARIA o cómo se ve."""
    body = _body(payload)
    return _runtime().set_presence(
        expression=body.get("expression"),
        channel=body.get("channel"),
        place=body.get("place"),
        mood=body.get("mood"),
        talking=body.get("talking"),
    )


@router.get("/api/autonomy/persona")
async def autonomy_persona() -> Dict[str, Any]:
    """Quién es ARIA."""
    return _runtime().persona()


@router.post("/api/autonomy/persona")
async def autonomy_set_persona(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Cambia quién es ARIA (nombre, tono, intereses)."""
    return _runtime().set_persona(_body(payload))


# ── La agenda ──────────────────────────────────────────────────────────


@router.get("/api/autonomy/agenda")
async def autonomy_agenda() -> Dict[str, Any]:
    """Lo que ARIA tiene entre manos."""
    return _runtime().agenda()


@router.post("/api/autonomy/agenda")
async def autonomy_agenda_add(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Apunta un objetivo: ARIA lo seguirá sola aunque nadie se lo recuerde."""
    body = _body(payload)
    return _runtime().agenda_add(
        str(body.get("goal", "")), str(body.get("reason", ""))
    )


@router.delete("/api/autonomy/agenda/{initiative_id}")
async def autonomy_agenda_drop(initiative_id: int) -> Dict[str, Any]:
    """Suelta un objetivo de la agenda."""
    return _runtime().agenda_drop(initiative_id)


# ── Los eventos ────────────────────────────────────────────────────────


@router.get("/api/autonomy/events")
async def autonomy_events(since: Optional[float] = None) -> Dict[str, Any]:
    """Lo último que ha pasado en los escenarios."""
    return _runtime().events(since=since)


@router.post("/api/autonomy/events")
async def autonomy_ingest_event(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Un escenario informa de algo: ARIA se entera y decide."""
    body = _body(payload)
    return _runtime().ingest(
        str(body.get("kind", "chat")),
        str(body.get("text", "")),
        str(body.get("source", "escritorio")),
        body.get("payload") or {},
    )


# ── Hablar y actuar ────────────────────────────────────────────────────


@router.post("/api/autonomy/speak")
async def autonomy_speak(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """ARIA dice algo por su cuenta."""
    body = _body(payload)
    return _runtime().speak(str(body.get("topic") or ""))


@router.post("/api/autonomy/act")
async def autonomy_act(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """ARIA hace algo concreto ahora: una skill o una frase."""
    body = _body(payload)
    return _runtime().act(
        action=str(body.get("action", "")),
        topic=body.get("topic"),
        skill_id=body.get("skill_id"),
        input=body.get("input") or {},
    )


@router.post("/api/autonomy/tick")
async def autonomy_tick(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Fuerza una vuelta del runtime."""
    body = _body(payload)
    return await asyncio.to_thread(_runtime().tick, bool(body.get("reactive", False)))


@router.post("/api/autonomy/permissions")
async def autonomy_permissions(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """El freno de seguridad: con `allow_external: false` no toca el exterior."""
    body = _body(payload)
    allow = body.get("allow_external")
    return _runtime().permissions(None if allow is None else bool(allow))


# ── Percepción y lecciones ────────────────────────────────────────────


@router.get("/api/perception")
async def perception() -> Dict[str, Any]:
    """Lo que ARIA ve ahora mismo: mundos, audiencia, pulsiones, agenda."""
    return _runtime().perception()


@router.get("/api/worlds")
async def worlds() -> Dict[str, Any]:
    """Los mundos que ARIA tiene abiertos, sin más envoltura."""
    snapshot = _runtime().perception()
    data = snapshot.get("perception") or {}
    return {
        "status": "ok",
        "worlds": [
            {
                "id": world.get("id", ""),
                "kind": world.get("kind", "local"),
                "label": world.get("label", ""),
                "capabilities": world.get("capabilities") or [],
                "connected": bool(world.get("connected")),
                "status": world.get("status", ""),
                "actions": 0,
                "pending": int(world.get("pending") or 0),
                "context": world.get("context") or {},
            }
            for world in (data.get("worlds") or [])
        ],
        "server": SERVER,
    }


@router.get("/api/lessons")
async def lessons() -> Dict[str, Any]:
    """Lo que ARIA ha aprendido."""
    return _runtime().lessons()


@router.post("/api/lessons")
async def lessons_create(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Enseña una regla a ARIA."""
    body = _body(payload)
    return _runtime().lessons_create(
        str(body.get("text", "")),
        str(body.get("kind", "regla")),
        str(body.get("source", "usuario")),
        float(body.get("weight", 1.0) or 1.0),
    )


@router.patch("/api/lessons/{lesson_id}")
async def lessons_update(lesson_id: int, payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """Silencia una lección: deja de entrar en el prompt de decisión."""
    body = _body(payload)
    suppressed = body.get("suppressed", True)
    return _runtime().mute_lesson(lesson_id, bool(suppressed))


@router.delete("/api/lessons/{lesson_id}")
async def lessons_delete(lesson_id: int) -> Dict[str, Any]:
    """Olvida una lección entera."""
    return _runtime().forget_lesson(lesson_id)


@router.post("/api/lessons/curate")
async def lessons_curate() -> Dict[str, Any]:
    """Fusiona lecciones repetidas y aparta las que ya no aplican."""
    return _runtime().lessons_curate()


@router.get("/api/autonomy/stream")
async def autonomy_stream():
    """La foto de lo que ARIA percibe, una vez cada poco.

    Es un flujo de texto: cada línea es un JSON con la percepción. No abre
    ningún puerto extra: vive en la misma conexión que ya hay.
    """
    async def _generator():
        while True:
            snapshot = await asyncio.to_thread(_runtime().perception)
            yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(_generator(), media_type="text/event-stream")
