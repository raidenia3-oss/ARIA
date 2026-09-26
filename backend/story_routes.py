"""Story Literary Base Routes — endpoints REST para la base literaria AURA/AME.

Endpoints bajo /api/story:
- POST   /api/story/works                           — crear obra
- GET    /api/story/works                           — listar obras
- GET    /api/story/works/{work_id}                 — obtener obra
- DELETE /api/story/works/{work_id}                 — borrar obra

- POST   /api/story/{work_id}/characters/{char_id}  — crear/actualizar personaje
- GET    /api/story/{work_id}/characters/{char_id}  — obtener personaje
- GET    /api/story/{work_id}/characters            — listar personajes
- DELETE /api/story/{work_id}/characters/{char_id}  — borrar personaje

- POST   /api/story/{work_id}/canon                 — agregar evento canónico
- GET    /api/story/{work_id}/canon                 — listar eventos canónicos
- POST   /api/story/{work_id}/continuity            — agregar evento de continuidad
- GET    /api/story/{work_id}/continuity            — listar eventos de continuidad
- GET    /api/story/{work_id}/chronology            — cronología completa
- GET    /api/story/{work_id}/conflicts             — detectar conflictos canónicos

- POST   /api/story/{work_id}/chapters              — crear capítulo
- GET    /api/story/{work_id}/chapters              — listar capítulos
- GET    /api/story/{work_id}/chapters/{chapter_id} — obtener capítulo
- PUT    /api/story/{work_id}/chapters/{chapter_id} — actualizar estado
- POST   /api/story/{work_id}/chapters/{chapter_id}/scenes — agregar escena

- POST   /api/story/{work_id}/check-consistency    — validar coherencia
- GET    /api/story/{work_id}/context-prompt       — obtener system prompt enriquecido

- POST   /api/story/sessions/{session_id}/context   — vincular sesión a obra+personaje
- DELETE /api/story/sessions/{session_id}/context   — desvincular sesión
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import io
import json
import os
import re
import tempfile
import time
import shutil
from fastapi import APIRouter, HTTPException, Query, Response

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.consistency_checker import StoryConsistencyChecker
from backend.story_memory.story_context import StoryContextManager
from backend.story_memory.session_context import set_session_context, get_session_context, clear_session_context
from backend.story_memory.versioning import get_snapshot_engine
from backend.story_memory.vault_backup import get_vault_backup as _get_vault_backup
from backend.story_memory.vector_rag import get_vector_engine, set_engine_store_path as set_vector_store_path
from backend.story_memory.graph_manager import get_graph_manager, GraphManager, RelationshipType, FactionType
from backend.story_memory.timeline_manager import get_timeline_manager, TimelineManager, TimelineEventType, TemporalRelation

router = APIRouter(prefix="/api/story", tags=["story-memory"])

storage = StoryStorage()
character_bible = CharacterBible()
canon_tracker = CanonTracker()
chapter_planner = ChapterPlanner()
consistency_checker = StoryConsistencyChecker()
context_manager = StoryContextManager()


@router.post("/works")
async def create_work(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    work_id = str(payload.get("work_id", ""))
    title = str(payload.get("title", ""))
    if not work_id or not title:
        raise HTTPException(status_code=422, detail="work_id and title are required")
    return storage.create_work(
        work_id=work_id,
        title=title,
        universe=str(payload.get("universe", "")),
        description=str(payload.get("description", "")),
        author=str(payload.get("author", "")),
    )


@router.get("/works")
async def list_works() -> Dict[str, Any]:
    works = storage.list_works()
    return {"works": works, "count": len(works)}


@router.get("/works/{work_id}")
async def get_work(work_id: str) -> Dict[str, Any]:
    work = storage.get_work(work_id)
    if not work:
        raise HTTPException(status_code=404, detail="work_not_found")
    return work


@router.delete("/works/{work_id}")
async def delete_work(work_id: str) -> Dict[str, Any]:
    return storage.clear_work(work_id)


@router.post("/{work_id}/characters/{char_id}")
async def upsert_character(work_id: str, char_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    char = character_bible.create(
        work_id=work_id,
        char_id=char_id,
        name=str(payload.get("name", char_id)),
        voice=str(payload.get("voice", "")),
        personality=payload.get("personality"),
        objectives=payload.get("objectives"),
        conflicts=payload.get("conflicts"),
        relationships=payload.get("relationships"),
        aliases=payload.get("aliases"),
        species=str(payload.get("species", "")),
        age=payload.get("age"),
        backstory=str(payload.get("backstory", "")),
    )
    return char


@router.get("/{work_id}/characters/{char_id}")
async def get_character(work_id: str, char_id: str) -> Dict[str, Any]:
    char = character_bible.get(work_id, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="character_not_found")
    return char


@router.get("/{work_id}/characters")
async def list_characters(work_id: str, name: Optional[str] = Query(None)) -> Dict[str, Any]:
    if name:
        char = character_bible.get_by_name(work_id, name)
        if char:
            return {"characters": [char], "count": 1}
        return {"characters": [], "count": 0}
    chars = character_bible.list(work_id)
    return {"characters": chars, "count": len(chars)}


@router.delete("/{work_id}/characters/{char_id}")
async def delete_character(work_id: str, char_id: str) -> Dict[str, Any]:
    return character_bible.delete(work_id, char_id)


@router.post("/{work_id}/canon")
async def add_canon_event(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return canon_tracker.add_canon_event(
        work_id=work_id,
        description=str(payload.get("description", "")),
        timestamp=float(payload.get("timestamp", 0)),
        scene_ref=str(payload.get("scene_ref", "")),
        source=str(payload.get("source", "user")),
    )


@router.get("/{work_id}/canon")
async def get_canon_events(work_id: str) -> Dict[str, Any]:
    events = canon_tracker.get_canon_events(work_id)
    return {"events": events, "count": len(events)}


@router.post("/{work_id}/continuity")
async def add_continuity_event(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return canon_tracker.add_continuity_event(
        work_id=work_id,
        description=str(payload.get("description", "")),
        timestamp=float(payload.get("timestamp", 0)),
        scene_ref=str(payload.get("scene_ref", "")),
        source=str(payload.get("source", "user")),
    )


@router.get("/{work_id}/continuity")
async def get_continuity_events(work_id: str) -> Dict[str, Any]:
    events = canon_tracker.get_continuity_events(work_id)
    return {"events": events, "count": len(events)}


@router.get("/{work_id}/chronology")
async def get_chronology(work_id: str, max_events: int = Query(50)) -> Dict[str, Any]:
    events = canon_tracker.get_chronology(work_id, max_events=max_events)
    return {"events": events, "count": len(events)}


@router.get("/{work_id}/conflicts")
async def get_conflicts(work_id: str) -> Dict[str, Any]:
    conflicts = canon_tracker.find_conflicts(work_id)
    return {"conflicts": conflicts, "count": len(conflicts)}


@router.post("/{work_id}/chapters")
async def create_chapter(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return chapter_planner.create_chapter(
        work_id=work_id,
        title=str(payload.get("title", "")),
        order=int(payload.get("order", 0)),
        beat_summary=str(payload.get("beat_summary", "")),
        scenes=payload.get("scenes"),
        related_canon=payload.get("related_canon"),
    )


@router.get("/{work_id}/chapters")
async def list_chapters(work_id: str) -> Dict[str, Any]:
    chapters = chapter_planner.list_chapters(work_id)
    progress = chapter_planner.get_progress(work_id)
    return {"chapters": chapters, "count": len(chapters), "progress": progress}


@router.get("/{work_id}/chapters/{chapter_id}")
async def get_chapter(work_id: str, chapter_id: str) -> Dict[str, Any]:
    chapter = chapter_planner.get_chapter(work_id, chapter_id)
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter_not_found")
    return chapter


@router.put("/{work_id}/chapters/{chapter_id}")
async def update_chapter(work_id: str, chapter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    status = str(payload.get("status", ""))
    if not status:
        raise HTTPException(status_code=422, detail="status is required")
    return chapter_planner.update_chapter_status(work_id, chapter_id, status)


@router.post("/{work_id}/chapters/{chapter_id}/scenes")
async def add_scene(work_id: str, chapter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    scene = payload.get("scene", {})
    if not scene:
        raise HTTPException(status_code=422, detail="scene is required")
    return chapter_planner.add_scene(work_id, chapter_id, scene)


@router.post("/{work_id}/check-consistency")
async def check_consistency(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    char_id = str(payload.get("char_id", ""))
    text = str(payload.get("text", ""))
    if not char_id or not text:
        raise HTTPException(status_code=422, detail="char_id and text are required")
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return consistency_checker.check_full_consistency(work_id, char_id, text)


@router.get("/{work_id}/context-prompt")
async def get_context_prompt(
    work_id: str,
    character_id: str = Query(...),
    base_prompt: str = Query("Eres AURA, un asistente de IA avanzado."),
) -> Dict[str, Any]:
    """Devuelve el system prompt enriquecido para chat dentro de personaje."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    char = character_bible.get(work_id, character_id)
    if not char:
        raise HTTPException(status_code=404, detail="character_not_found")
    prompt = context_manager.build_system_prompt(
        work_id=work_id,
        character_id=character_id,
        base_prompt=base_prompt,
    )
    return {"status": "ok", "system_prompt": prompt}


@router.post("/sessions/{session_id}/context")
async def bind_session(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    work_id = str(payload.get("work_id", ""))
    character_id = str(payload.get("character_id", ""))
    if not work_id or not character_id:
        raise HTTPException(status_code=422, detail="work_id and character_id are required")
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    char = character_bible.get(work_id, character_id)
    if not char:
        raise HTTPException(status_code=404, detail="character_not_found")
    ctx = set_session_context(session_id, work_id, character_id, payload.get("extra"))
    return {"status": "bound", "session_id": session_id, "context": ctx}


@router.delete("/sessions/{session_id}/context")
async def unbind_session(session_id: str) -> Dict[str, Any]:
    return clear_session_context(session_id)


@router.get("/sessions/{session_id}/context")
async def get_session_ctx(session_id: str) -> Dict[str, Any]:
    ctx = get_session_context(session_id)
    if not ctx:
        return {"status": "no_context", "active": False}
    return {"status": "active", "active": True, "context": ctx}


@router.get("/backup")
async def story_backup() -> Dict[str, Any]:
    """Exporta la base literaria completa para backup (Discord Vault Service).

    Serializa works, characters, canon, chronology y session contexts
    como un único objeto JSON. No incluye tokens ni secretos.
    """
    result: Dict[str, Any] = {"works": []}
    for work in storage.list_works():
        work_id = work.get("work_id", "")
        w: Dict[str, Any] = {
            "work_id": work_id,
            "title": work.get("title", ""),
            "universe": work.get("universe", ""),
            "description": work.get("description", ""),
            "author": work.get("author", ""),
            "created_at": work.get("created_at"),
            "updated_at": work.get("updated_at"),
            "characters": character_bible.list(work_id),
            "canon": canon_tracker.get_all_events(work_id),
            "chronology": canon_tracker.get_chronology(work_id),
            "chapters": chapter_planner.list_chapters(work_id),
        }
        result["works"].append(w)

    from backend.story_memory.session_context import _session_contexts, _ensure_loaded
    _ensure_loaded()
    import threading as _t
    with _t.Lock():
        sessions = {k: dict(v) for k, v in _session_contexts.items()}
    result["sessions"] = sessions
    result["timestamp"] = __import__("time").time()
    return result


# -- Literary Snapshot Engine (Git-lite versioning) ---------------------------


@router.post("/{work_id}/snapshots", status_code=201)
async def create_snapshot(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea un punto de restauración del estado actual de una obra."""
    message = str(payload.get("message", "checkpoint"))
    author = str(payload.get("author", "ame"))
    branch = str(payload.get("branch", "main"))
    engine = get_snapshot_engine()
    return engine.create_snapshot(work_id, message=message, author=author, branch=branch)


@router.get("/{work_id}/snapshots")
async def list_snapshots(work_id: str, branch: str = "main") -> Dict[str, Any]:
    """Lista los snapshots de una obra (opcionalmente por rama)."""
    engine = get_snapshot_engine()
    snaps = engine.list_snapshots(work_id, branch=branch)
    return {"status": "ok", "work_id": work_id, "branch": branch, "snapshots": snaps}


@router.get("/{work_id}/snapshots/{snapshot_id}")
async def get_snapshot(work_id: str, snapshot_id: str, branch: str = "main") -> Dict[str, Any]:
    """Recupera un snapshot por ID."""
    engine = get_snapshot_engine()
    snap = engine.get_snapshot(work_id, snapshot_id, branch=branch)
    if not snap:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return {"status": "ok", "snapshot": snap}


@router.post("/{work_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(work_id: str, snapshot_id: str) -> Dict[str, Any]:
    """Restaura el estado de una obra desde un snapshot a una nueva rama."""
    engine = get_snapshot_engine()
    return engine.restore_snapshot(work_id, snapshot_id)


@router.get("/{work_id}/branches")
async def list_branches(work_id: str) -> Dict[str, Any]:
    """Lista las ramas narrativas de una obra."""
    engine = get_snapshot_engine()
    return {"status": "ok", "work_id": work_id, "branches": engine.list_branches(work_id)}


@router.get("/{work_id}/snapshots/diff")
async def diff_snapshots(
    work_id: str,
    snapshot_a: str = Query(..., alias="a"),
    snapshot_b: str = Query(..., alias="b"),
    branch: str = Query("main"),
) -> Dict[str, Any]:
    """Calcula el diff entre dos snapshots de una obra."""
    engine = get_snapshot_engine()
    return engine.diff_snapshots(work_id, snapshot_a, snapshot_b, branch=branch)


@router.get("/{work_id}/snapshots/{snapshot_id}/export")
async def export_snapshot(work_id: str, snapshot_id: str, branch: str = "main") -> Dict[str, Any]:
    """Exporta un snapshot como JSON para respaldo en Discord Vault."""
    engine = get_snapshot_engine()
    json_str = engine.export_snapshot(work_id, snapshot_id, branch=branch)
    if not json_str:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return {"status": "ok", "work_id": work_id, "snapshot_id": snapshot_id, "data": json.loads(json_str)}


# -- Discord Vault Auto-Backup (Bloque 32 func. 3 / Bloque 30) -------------------


@router.get("/vault/status")
async def vault_backup_status() -> Dict[str, Any]:
    """Estado del servicio de respaldo a la Bóveda de Discord (sin exponer secretos)."""
    return _get_vault_backup().status()


@router.post("/{work_id}/snapshots/backup")
async def backup_snapshots_to_vault(
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Empaqueta y sube (cifrado) los snapshots recientes a la Bóveda de Discord.

    El disparo es asíncrono (no bloquea el hilo principal). Cuerpo opcional:
      {"branch": "main", "recent_n": 5, "sync": false}
    Si ``sync: true`` se espera la subida síncrona (para diagnóstico).
    """
    branch = str(payload.get("branch", "main"))
    recent_n = int(payload.get("recent_n", 5))
    sync = bool(payload.get("sync", False))
    vault = _get_vault_backup()
    if sync:
        return vault.push(work_id, branch=branch, recent_n=recent_n)
    return vault.push_async(work_id, branch=branch, recent_n=recent_n)


# -- Bloque 41: Vector RAG local (indexación + búsqueda semántica) -------------------


async def _vector_engine():
    """Lazy engine: inicializa el VectorRAGEngine con el store del backend."""
    set_vector_store_path(os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory")))
    return get_vector_engine()


@router.post("/{work_id}/semantic-index", status_code=201)
async def semantic_index_work(work_id: str) -> Dict[str, Any]:
    """(Re)construye el índice vectorial local de una obra.

    Recolecta Character Bible, canon, continuity y chapters; los fragmenta y
    vectoriza (offline) persistiendo el índice on-disk. No usa nube.
    """
    engine = await _vector_engine()
    result = engine.index_work(work_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("error", "index_failed"))
    return result


@router.get("/{work_id}/semantic-index/status")
async def semantic_index_status(work_id: str) -> Dict[str, Any]:
    """Estado del índice semántico local de una obra."""
    engine = await _vector_engine()
    status = engine.get_status(work_id)
    return {"status": "ok", **status}


@router.post("/{work_id}/semantic-search")
async def semantic_search(
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Búsqueda semántica local sobre el lore de una obra.

    Cuerpo: {"query": str, "top_k": int (default 5)}
    Retorna los fragments más relevantes (similitud coseno) + contexto inyectable.
    """
    query = str(payload.get("query", "")).strip()
    top_k = int(payload.get("top_k", 5))
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    engine = await _vector_engine()
    res = engine.semantic_search(work_id, query, top_k=top_k)
    return res


@router.post("/{work_id}/context-inject")
async def context_inject(
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Jan Context Injector — inyecta lore relevante para prompts a Jan (local).

    Cuerpo: {"query": str, "top_k": int, "max_chars": int}
    Retorna {"context": str, "results": [...]} listo para adjuntar al system prompt.
    """
    query = str(payload.get("query", "")).strip()
    top_k = int(payload.get("top_k", 5))
    max_chars = int(payload.get("max_chars", 2000))
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    engine = await _vector_engine()
    res = engine.semantic_search(work_id, query, top_k=top_k)
    context = engine._build_context(res["results"], max_chars=max_chars)
    return {"context": context, "results": res["results"]}


# -- Bloque 42: Local Manuscript Compiler & Export Engine -------------------------


def _get_export_engine():
    from backend.export.compiler import get_export_engine as _get_engine
    return _get_engine()


@router.get("/{work_id}/export/formats")
async def list_export_formats(work_id: str) -> Dict[str, Any]:
    """Lista formatos de exportación soportados."""
    engine = _get_export_engine()
    return {"status": "ok", "formats": engine.get_supported_formats()}


@router.post("/{work_id}/export/{format}")
async def export_manuscript(
    work_id: str,
    format: str,
    payload: Dict[str, Any],
) -> Response:
    """Exporta el manuscrito compilado al formato solicitado (epub, markdown, pdf).

    Cuerpo opcional:
    {
        "output_filename": "mi_obra.epub"  # opcional, se genera uno por defecto
    }

    Devuelve el archivo binario para descarga directa.
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    engine = _get_export_engine()
    supported = engine.get_supported_formats()
    if format not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported: {supported}")

    output_filename = payload.get("output_filename") if isinstance(payload, dict) else None
    if not output_filename:
        work = storage.get_work(work_id)
        safe_title = re.sub(r"[^A-Za-z0-9_-]", "_", work.get("title", work_id))
        output_filename = f"{safe_title}.{format}"

    # For markdown, we need a temp directory, not a file
    if format == "markdown":
        temp_dir = tempfile.mkdtemp(prefix=f"export_{work_id}_")
        temp_path = temp_dir
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
            temp_path = tmp.name

    try:
        result = engine.compile_and_export(work_id, format, temp_path)
        media_type = {
            "epub": "application/epub+zip",
            "pdf": "application/pdf",
            "markdown": "application/zip",
        }.get(format, "application/octet-stream")

        if format == "markdown":
            # Zip the markdown directory
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_path)
                        zipf.write(file_path, arcname)
            content = zip_buffer.getvalue()
        else:
            with open(temp_path, "rb") as f:
                content = f.read()

        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if format == "markdown":
            import shutil
            if os.path.exists(temp_path):
                shutil.rmtree(temp_path, ignore_errors=True)
        else:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass


@router.post("/{work_id}/export/{format}/async")
async def export_manuscript_async(
    work_id: str,
    format: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Exportación asíncrona en segundo plano (no bloquea).

    Retorna un job_id para consultar estado y descargar luego.
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    engine = _get_export_engine()
    supported = engine.get_supported_formats()
    if format not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported: {supported}")

    output_filename = payload.get("output_filename") if isinstance(payload, dict) else None
    if not output_filename:
        work = storage.get_work(work_id)
        safe_title = re.sub(r"[^A-Za-z0-9_-]", "_", work.get("title", work_id))
        output_filename = f"{safe_title}.{format}"

    job_id = f"export_{work_id}_{format}_{int(time.time() * 1000)}"

    def _export_task():
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
                temp_path = tmp.name
            result = engine.compile_and_export(work_id, format, temp_path)
            final_path = os.path.join(engine.compiler.store_dir, "exports", output_filename)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            shutil.move(temp_path, final_path)
            _export_jobs[job_id] = {
                "status": "completed",
                "path": final_path,
                "filename": output_filename,
                "work_id": work_id,
            }
        except Exception as e:
            _export_jobs[job_id] = {"status": "failed", "error": str(e), "work_id": work_id}

    import threading
    thread = threading.Thread(target=_export_task, daemon=True)
    thread.start()

    _export_jobs[job_id] = {"status": "processing", "started_at": time.time(), "work_id": work_id}
    return {"status": "accepted", "job_id": job_id, "format": format}


@router.get("/{work_id}/export/jobs/{job_id}")
async def get_export_job(work_id: str, job_id: str) -> Dict[str, Any]:
    """Consulta estado de un job de exportación asíncrona."""
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.get("work_id") and job["work_id"] != work_id:
        raise HTTPException(status_code=403, detail="work_mismatch")
    return {"status": "ok", "job": job}


@router.get("/{work_id}/export/jobs/{job_id}/download")
async def download_export_job(work_id: str, job_id: str) -> Response:
    """Descarga el archivo generado por un job completado."""
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed: {job.get('status')}")
    if job.get("work_id") and job["work_id"] != work_id:
        raise HTTPException(status_code=403, detail="work_mismatch")

    path = job.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file_not_found")

    filename = job.get("filename", "export")
    with open(path, "rb") as f:
        content = f.read()

    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_export_jobs: Dict[str, Dict[str, Any]] = {}


# -- Bloque 43: Local Character Relationship Graph & Faction Matrix -----------------------


def _get_graph_manager() -> GraphManager:
    return get_graph_manager()


@router.get("/{work_id}/relationships")
async def get_relationships(work_id: str, char_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Obtiene la red de relaciones de una obra o de un personaje específico.

    Query params:
      - char_id (opcional): si se proporciona, devuelve solo relaciones de ese personaje
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    if char_id:
        return gm.get_relationships(work_id, char_id)
    return gm.get_all_relationships(work_id)


@router.post("/{work_id}/relationships")
async def add_relationship(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Añade o actualiza una relación entre dos personajes.

    Cuerpo:
    {
        "source_id": "char_1",
        "target_id": "char_2",
        "rel_type": "ally|friend|family|mentor|rival|enemy|loyal_to|betrayed|romantic|subordinate|neutral",
        "weight": 0.8,              # opcional, -1.0 a 1.0
        "bidirectional": false,     # opcional
        "evidence": ["canon:evt_1"], # opcional, referencias
        "metadata": {}              # opcional
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    source_id = str(payload.get("source_id", ""))
    target_id = str(payload.get("target_id", ""))
    rel_type_str = str(payload.get("rel_type", "neutral"))

    if not source_id or not target_id:
        raise HTTPException(status_code=422, detail="source_id and target_id are required")

    try:
        rel_type = RelationshipType(rel_type_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid rel_type: {rel_type_str}")

    weight = payload.get("weight")
    if weight is not None:
        weight = float(weight)
        if not -1.0 <= weight <= 1.0:
            raise HTTPException(status_code=422, detail="weight must be between -1.0 and 1.0")

    bidirectional = bool(payload.get("bidirectional", False))
    evidence = payload.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        raise HTTPException(status_code=422, detail="evidence must be a list")

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise HTTPException(status_code=422, detail="metadata must be an object")

    gm = _get_graph_manager()
    return gm.add_relationship(
        work_id=work_id,
        source_id=source_id,
        target_id=target_id,
        rel_type=rel_type,
        weight=weight,
        bidirectional=bidirectional,
        evidence=evidence,
        metadata=metadata,
    )


@router.put("/{work_id}/relationships/{source_id}/{target_id}")
async def update_relationship(
    work_id: str,
    source_id: str,
    target_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Actualiza una relación existente."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    rel_type = None
    if "rel_type" in payload:
        try:
            rel_type = RelationshipType(str(payload["rel_type"]))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid rel_type: {payload['rel_type']}")

    weight = payload.get("weight")
    if weight is not None:
        weight = float(weight)
        if not -1.0 <= weight <= 1.0:
            raise HTTPException(status_code=422, detail="weight must be between -1.0 and 1.0")

    evidence = payload.get("evidence")
    metadata = payload.get("metadata")

    return gm.update_relationship(
        work_id=work_id,
        source_id=source_id,
        target_id=target_id,
        rel_type=rel_type,
        weight=weight,
        evidence=evidence,
        metadata=metadata,
    )


@router.delete("/{work_id}/relationships/{source_id}/{target_id}")
async def remove_relationship(work_id: str, source_id: str, target_id: str) -> Dict[str, Any]:
    """Elimina una relación."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.remove_relationship(work_id, source_id, target_id)


@router.get("/{work_id}/relationships/summary/{char_id}")
async def get_relationship_summary(work_id: str, char_id: str) -> Dict[str, Any]:
    """Resumen narrativo de relaciones para inyección en prompts (Jan)."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.get_relationship_summary(work_id, char_id)


@router.post("/{work_id}/relationships/check-conflict")
async def check_relationship_conflict(
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Verifica si una acción propuesta contradice relaciones establecidas.

    Cuerpo:
    {
        "char_id": "protagonista",
        "proposed_action": "traiciona a su mentor",
        "target_char_id": "mentor"  # opcional
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    char_id = str(payload.get("char_id", ""))
    proposed_action = str(payload.get("proposed_action", ""))
    target_char_id = payload.get("target_char_id")

    if not char_id or not proposed_action:
        raise HTTPException(status_code=422, detail="char_id and proposed_action are required")

    gm = _get_graph_manager()
    return gm.check_relationship_conflict(work_id, char_id, proposed_action, target_char_id)


@router.get("/{work_id}/relationships/graph")
async def export_relationship_graph(work_id: str) -> Dict[str, Any]:
    """Exporta datos completos del grafo para visualización (nodos, aristas, facciones, matrices)."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.export_graph_data(work_id)


# -- Faction Endpoints --


@router.get("/{work_id}/factions")
async def list_factions(work_id: str) -> Dict[str, Any]:
    """Lista todas las facciones de una obra."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.list_factions(work_id)


@router.get("/{work_id}/factions/{faction_id}")
async def get_faction(work_id: str, faction_id: str) -> Dict[str, Any]:
    """Obtiene detalles de una facción específica."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.get_faction(work_id, faction_id)


@router.post("/{work_id}/factions")
async def create_faction(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea una nueva facción.

    Cuerpo:
    {
        "faction_id": "faccion_1",
        "name": "La Orden del Alba",
        "faction_type": "political|military|religious|criminal|family_clan|guild|secret_society|independent",
        "description": "Descripción opcional",
        "leader_id": "char_1",      # opcional
        "ideology": ["honor", "justicia"]  # opcional
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    faction_id = str(payload.get("faction_id", ""))
    name = str(payload.get("name", ""))
    faction_type_str = str(payload.get("faction_type", "independent"))

    if not faction_id or not name:
        raise HTTPException(status_code=422, detail="faction_id and name are required")

    try:
        faction_type = FactionType(faction_type_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid faction_type: {faction_type_str}")

    description = str(payload.get("description", ""))
    leader_id = payload.get("leader_id")
    if leader_id:
        leader_id = str(leader_id)

    ideology = payload.get("ideology")
    if ideology is not None and not isinstance(ideology, list):
        raise HTTPException(status_code=422, detail="ideology must be a list")

    gm = _get_graph_manager()
    return gm.create_faction(
        work_id=work_id,
        faction_id=faction_id,
        name=name,
        faction_type=faction_type,
        description=description,
        leader_id=leader_id,
        ideology=ideology,
    )


@router.put("/{work_id}/factions/{faction_id}")
async def update_faction(work_id: str, faction_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza una facción existente."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.update_faction(
        work_id=work_id,
        faction_id=faction_id,
        name=payload.get("name"),
        description=payload.get("description"),
        leader_id=payload.get("leader_id"),
        allies=payload.get("allies"),
        enemies=payload.get("enemies"),
        territory=payload.get("territory"),
        ideology=payload.get("ideology"),
    )


@router.delete("/{work_id}/factions/{faction_id}")
async def delete_faction(work_id: str, faction_id: str) -> Dict[str, Any]:
    """Elimina una facción."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.delete_faction(work_id, faction_id)


@router.post("/{work_id}/factions/{faction_id}/members/{char_id}")
async def add_character_to_faction(work_id: str, faction_id: str, char_id: str) -> Dict[str, Any]:
    """Asigna un personaje a una facción."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.add_character_to_faction(work_id, char_id, faction_id)


@router.delete("/{work_id}/factions/{faction_id}/members/{char_id}")
async def remove_character_from_faction(work_id: str, faction_id: str, char_id: str) -> Dict[str, Any]:
    """Remueve un personaje de su facción actual."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    gm = _get_graph_manager()
    return gm.remove_character_from_faction(work_id, char_id)


# -- Bloque 44: Local Narrative Timeline & Chronology Mapper ---------------------------


def _get_timeline_manager() -> TimelineManager:
    return get_timeline_manager()


@router.get("/{work_id}/timeline")
async def get_timeline(work_id: str) -> Dict[str, Any]:
    """Obtiene la línea de tiempo completa exportada para visualización."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.export_timeline(work_id)


@router.get("/{work_id}/timeline/stats")
async def get_timeline_stats(work_id: str) -> Dict[str, Any]:
    """Estadísticas de la línea de tiempo."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.get_timeline_stats(work_id)


@router.get("/{work_id}/timeline/chronology")
async def get_chronology(
    work_id: str,
    max_events: int = Query(50),
    event_type: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Obtiene la cronología ordenada de eventos."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    if event_type:
        try:
            et = TimelineEventType(event_type)
            result = tm.list_events(work_id, event_type=et, limit=max_events)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid event_type: {event_type}")
    else:
        result = tm.get_chronology(work_id, max_events=max_events)
    return result


@router.post("/{work_id}/timeline/events")
async def create_timeline_event(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea un nuevo evento en la línea de tiempo.

    Cuerpo:
    {
        "title": "Evento importante",
        "description": "Descripción detallada",
        "event_type": "canon|continuity|chapter|scene|flashback|flashforward|backstory|prologue|epilogue",
        "timestamp": 1234567890.0,     # opcional, epoch seconds
        "relative_order": 0,           # opcional
        "duration": 3600.0,            # opcional, segundos
        "chapter_id": "ch_1",          # opcional
        "scene_id": "sc_1",            # opcional
        "characters": ["char_1"],      # opcional
        "factions": ["faction_1"],     # opcional
        "location": "Ciudad",          # opcional
        "tags": ["importante"],        # opcional
        "certainty": "canon",          # opcional
        "source": "user",              # opcional
        "thread_id": "main"            # opcional
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()

    title = str(payload.get("title", ""))
    description = str(payload.get("description", ""))
    event_type_str = str(payload.get("event_type", "canon"))

    if not title or not description:
        raise HTTPException(status_code=422, detail="title and description are required")

    try:
        event_type = TimelineEventType(event_type_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid event_type: {event_type_str}")

    timestamp = payload.get("timestamp")
    if timestamp is not None:
        timestamp = float(timestamp)

    relative_order = payload.get("relative_order", 0)
    if relative_order is not None:
        relative_order = int(relative_order)

    duration = payload.get("duration")
    if duration is not None:
        duration = float(duration)

    characters = payload.get("characters")
    if characters is not None and not isinstance(characters, list):
        raise HTTPException(status_code=422, detail="characters must be a list")

    factions = payload.get("factions")
    if factions is not None and not isinstance(factions, list):
        raise HTTPException(status_code=422, detail="factions must be a list")

    tags = payload.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise HTTPException(status_code=422, detail="tags must be a list")

    thread_id = payload.get("thread_id")

    return tm.add_event(
        work_id=work_id,
        title=title,
        description=description,
        event_type=event_type,
        timestamp=timestamp or 0.0,
        relative_order=relative_order,
        duration=duration,
        chapter_id=payload.get("chapter_id"),
        scene_id=payload.get("scene_id"),
        characters=characters,
        factions=factions,
        location=payload.get("location"),
        tags=tags,
        certainty=str(payload.get("certainty", "canon")),
        source=str(payload.get("source", "user")),
        thread_id=thread_id,
    )


@router.get("/{work_id}/timeline/events")
async def list_timeline_events(
    work_id: str,
    event_type: Optional[str] = Query(None),
    character_id: Optional[str] = Query(None),
    faction_id: Optional[str] = Query(None),
    start_time: Optional[float] = Query(None),
    end_time: Optional[float] = Query(None),
    limit: int = Query(100),
) -> Dict[str, Any]:
    """Lista eventos con filtros opcionales."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()

    et = None
    if event_type:
        try:
            et = TimelineEventType(event_type)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid event_type: {event_type}")

    return tm.list_events(
        work_id=work_id,
        event_type=et,
        character_id=character_id,
        faction_id=faction_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )


@router.get("/{work_id}/timeline/events/{event_id}")
async def get_timeline_event(work_id: str, event_id: str) -> Dict[str, Any]:
    """Obtiene un evento específico."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.get_event(work_id, event_id)


@router.put("/{work_id}/timeline/events/{event_id}")
async def update_timeline_event(work_id: str, event_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza un evento existente."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()

    event_type = None
    if "event_type" in payload:
        try:
            event_type = TimelineEventType(str(payload["event_type"]))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid event_type: {payload['event_type']}")

    timestamp = payload.get("timestamp")
    if timestamp is not None:
        timestamp = float(timestamp)

    relative_order = payload.get("relative_order")
    if relative_order is not None:
        relative_order = int(relative_order)

    duration = payload.get("duration")
    if duration is not None:
        duration = float(duration)

    characters = payload.get("characters")
    if characters is not None and not isinstance(characters, list):
        raise HTTPException(status_code=422, detail="characters must be a list")

    factions = payload.get("factions")
    if factions is not None and not isinstance(factions, list):
        raise HTTPException(status_code=422, detail="factions must be a list")

    tags = payload.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise HTTPException(status_code=422, detail="tags must be a list")

    return tm.update_event(
        work_id=work_id,
        event_id=event_id,
        title=payload.get("title"),
        description=payload.get("description"),
        event_type=event_type,
        timestamp=timestamp,
        relative_order=relative_order,
        duration=duration,
        characters=characters,
        factions=factions,
        location=payload.get("location"),
        tags=tags,
        certainty=payload.get("certainty"),
    )


@router.delete("/{work_id}/timeline/events/{event_id}")
async def delete_timeline_event(work_id: str, event_id: str) -> Dict[str, Any]:
    """Elimina un evento de la línea de tiempo."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.delete_event(work_id, event_id)


# --- Timeline Links ---

@router.post("/{work_id}/timeline/links")
async def create_timeline_link(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea un enlace temporal entre dos eventos.

    Cuerpo:
    {
        "source_id": "evt_1",
        "target_id": "evt_2",
        "relation": "before|after|simultaneous|during|causes|caused_by|precedes|follows",
        "strength": 1.0,
        "evidence": ["canon:1"]
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    source_id = str(payload.get("source_id", ""))
    target_id = str(payload.get("target_id", ""))
    relation_str = str(payload.get("relation", "before"))

    if not source_id or not target_id:
        raise HTTPException(status_code=422, detail="source_id and target_id are required")

    try:
        relation = TemporalRelation(relation_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid relation: {relation_str}")

    strength = payload.get("strength", 1.0)
    if not 0.0 <= strength <= 1.0:
        raise HTTPException(status_code=422, detail="strength must be between 0.0 and 1.0")

    evidence = payload.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        raise HTTPException(status_code=422, detail="evidence must be a list")

    tm = _get_timeline_manager()
    return tm.add_link(
        work_id=work_id,
        source_id=source_id,
        target_id=target_id,
        relation=relation,
        strength=strength,
        evidence=evidence,
    )


@router.delete("/{work_id}/timeline/links")
async def delete_timeline_link(
    work_id: str,
    source_id: str = Query(...),
    target_id: str = Query(...),
    relation: str = Query(...),
) -> Dict[str, Any]:
    """Elimina un enlace temporal."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    try:
        rel = TemporalRelation(relation)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid relation: {relation}")

    tm = _get_timeline_manager()
    return tm.remove_link(work_id, source_id, target_id, rel)


@router.get("/{work_id}/timeline/links")
async def list_timeline_links(
    work_id: str,
    event_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Lista enlaces temporales."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.get_links(work_id, event_id)


# --- Narrative Threads ---

@router.get("/{work_id}/timeline/threads")
async def list_timeline_threads(work_id: str) -> Dict[str, Any]:
    """Lista todos los hilos narrativos."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.list_threads(work_id)


@router.post("/{work_id}/timeline/threads")
async def create_timeline_thread(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea un nuevo hilo narrativo (subtrama).

    Cuerpo:
    {
        "thread_id": "subplot_1",
        "name": "Subtrama Romántica",
        "description": "Desarrollo romántico paralelo",
        "color": "#E91E63",
        "character_ids": ["char_1", "char_2"],
        "is_main": false
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    thread_id = str(payload.get("thread_id", ""))
    name = str(payload.get("name", ""))

    if not thread_id or not name:
        raise HTTPException(status_code=422, detail="thread_id and name are required")

    tm = _get_timeline_manager()
    return tm.create_thread(
        work_id=work_id,
        thread_id=thread_id,
        name=name,
        description=str(payload.get("description", "")),
        color=str(payload.get("color", "#888888")),
        character_ids=payload.get("character_ids"),
        is_main=bool(payload.get("is_main", False)),
    )


@router.get("/{work_id}/timeline/threads/{thread_id}")
async def get_timeline_thread(work_id: str, thread_id: str) -> Dict[str, Any]:
    """Obtiene un hilo narrativo con sus eventos."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.get_thread(work_id, thread_id)


@router.put("/{work_id}/timeline/threads/{thread_id}")
async def update_timeline_thread(work_id: str, thread_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza un hilo narrativo."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.update_thread(
        work_id=work_id,
        thread_id=thread_id,
        name=payload.get("name"),
        description=payload.get("description"),
        color=payload.get("color"),
        character_ids=payload.get("character_ids"),
        is_main=payload.get("is_main"),
    )


@router.delete("/{work_id}/timeline/threads/{thread_id}")
async def delete_timeline_thread(work_id: str, thread_id: str) -> Dict[str, Any]:
    """Elimina un hilo narrativo."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.delete_thread(work_id, thread_id)


@router.post("/{work_id}/timeline/threads/{thread_id}/events/{event_id}")
async def add_event_to_thread(work_id: str, thread_id: str, event_id: str) -> Dict[str, Any]:
    """Añade un evento a un hilo narrativo."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.add_event_to_thread(work_id, thread_id, event_id)


# --- Chronology Validation (Jan Integration) ---

@router.post("/{work_id}/timeline/validate")
async def validate_chronology(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Valida que un evento propuesto no contradiga la cronología (Jan Chronology Validator).

    Cuerpo:
    {
        "event_id": "evt_new",
        "title": "Nuevo evento",
        "description": "El héroe muere",
        "event_type": "canon",
        "timestamp": 1234567890.0
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    tm = _get_timeline_manager()
    return tm.validate_chronology(work_id, payload)


@router.post("/{work_id}/timeline/check-sequence")
async def check_event_sequence(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Verifica que una secuencia de eventos sea cronológicamente coherente.

    Cuerpo:
    {
        "event_ids": ["evt_1", "evt_2", "evt_3"]
    }
    """
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")

    event_ids = payload.get("event_ids")
    if not event_ids or not isinstance(event_ids, list):
        raise HTTPException(status_code=422, detail="event_ids list is required")

    tm = _get_timeline_manager()
    return tm.check_event_sequence(work_id, event_ids)


# -- Bloque 45: Local Interactive Codex & World Gazetteer ---------------------

from backend.story_memory.gazetteer import get_gazetteer as _get_gazetteer_fn


def _get_gazetteer():
    return _get_gazetteer_fn()


@router.post("/{work_id}/codex", status_code=201)
async def codex_create(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Crea una ficha del codex / gacetera."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    title = str(payload.get("title", ""))
    if not title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    gz = _get_gazetteer()
    res = gz.create_entry(
        work_id, title,
        entry_type=payload.get("entry_type", "location"),
        description=str(payload.get("description", "")),
        x=float(payload.get("x", 0.0)), y=float(payload.get("y", 0.0)),
        region=str(payload.get("region", "")),
        climate=str(payload.get("climate", "unknown")),
        controlling_faction=str(payload.get("controlling_faction", "")),
        traits=payload.get("traits"), influence_radius=float(payload.get("influence_radius", 0.0)),
        tags=payload.get("tags"), entry_id=payload.get("entry_id"),
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=422, detail=res.get("error"))
    return res


@router.get("/{work_id}/codex")
async def codex_list(
    work_id: str, entry_type: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _get_gazetteer().list_entries(work_id, entry_type=entry_type, region=region)


@router.get("/{work_id}/codex/stats")
async def codex_stats(work_id: str) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _get_gazetteer().get_codex_stats(work_id)


@router.get("/{work_id}/codex/search/radius")
async def codex_radius(
    work_id: str, x: float = Query(0.0), y: float = Query(0.0),
    radius: float = Query(10.0),
) -> Dict[str, Any]:
    """Buscar locaciones por radio de influencia (coordenadas del mundo)."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _get_gazetteer().search_by_radius(work_id, x, y, radius)


@router.get("/{work_id}/codex/{entry_id}")
async def codex_get(work_id: str, entry_id: str) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _get_gazetteer().get_entry(work_id, entry_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail="entry_not_found")
    return res


@router.put("/{work_id}/codex/{entry_id}")
async def codex_update(work_id: str, entry_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _get_gazetteer().update_entry(work_id, entry_id, payload)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail="entry_not_found")
    return res


@router.delete("/{work_id}/codex/{entry_id}")
async def codex_delete(work_id: str, entry_id: str) -> Dict[str, Any]:
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _get_gazetteer().delete_entry(work_id, entry_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail="entry_not_found")
    return res


@router.get("/{work_id}/codex/{entry_id}/xrefs")
async def codex_xrefs(work_id: str, entry_id: str) -> Dict[str, Any]:
    """Referencias cruzadas lore <-> personajes/canon/capitulos."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _get_gazetteer().get_cross_references(work_id, entry_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail="entry_not_found")
    return res


@router.post("/{work_id}/codex/{entry_id}/link")
async def codex_link(work_id: str, entry_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Vincula artefacto/personaje/canon a una ficha. {kind, ref_id}."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    kind = str(payload.get("kind", ""))
    ref_id = str(payload.get("ref_id", ""))
    if not kind or not ref_id:
        raise HTTPException(status_code=422, detail="kind and ref_id are required")
    gz = _get_gazetteer()
    if kind == "artifact":
        res = gz.link_artifact(work_id, entry_id, ref_id)
    elif kind == "character":
        res = gz.link_character(work_id, entry_id, ref_id)
    elif kind == "canon":
        res = gz.link_canon(work_id, entry_id, ref_id)
    else:
        raise HTTPException(status_code=422, detail=f"invalid kind: {kind}")
    if res.get("status") == "error":
        raise HTTPException(status_code=404, detail="entry_not_found")
    return res


@router.post("/{work_id}/codex/check-spatial")
async def codex_check_spatial(work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Jan Spatial Consistency Checker: escena vs codex."""
    if not storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _get_gazetteer().check_spatial_consistency(work_id, payload)
