"""AURA Local Automated Backup & Version Snapshot Engine (BLOQUE 49).

Motor local de respaldos automatizados y control de versiones por instantáneas (*snapshots*).
Empaqueta de forma comprimida y segura el estado completo de la obra literaria:
- Capítulos, Character Bible, grafo de relaciones, gacetera, línea de tiempo, vectores RAG.

Almacenamiento: archivos ZIP en `<store_dir>/backups/work_<id>/snapshot_<timestamp>.zip`
Metadatos JSON: `<store_dir>/backups/work_<id>.backup_index.json`

Usa solo stdlib (zipfile, json, tarfile opcional). Sin dependencias externas.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.versioning import LiterarySnapshotEngine, get_snapshot_engine


# --- utilidades ---

def _now() -> float:
    return time.time()


def _iso(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts or _now()).isoformat(timespec="seconds")


def _safe_work_id(work_id: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# --- estructuras de datos ---

@dataclass
class SnapshotManifest:
    """Metadatos de una instantánea."""
    snapshot_id: str
    work_id: str
    created_at: float
    created_at_iso: str
    message: str
    author: str
    components: List[str] = field(default_factory=list)  # ej: ["characters", "canon", "timeline", ...]
    total_files: int = 0
    total_bytes: int = 0
    sha256: str = ""
    zip_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "work_id": self.work_id,
            "created_at": self.created_at,
            "created_at_iso": self.created_at_iso,
            "message": self.message,
            "author": self.author,
            "components": self.components,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "sha256": self.sha256,
            "zip_path": self.zip_path,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SnapshotManifest":
        return cls(
            snapshot_id=d["snapshot_id"],
            work_id=d["work_id"],
            created_at=d["created_at"],
            created_at_iso=d["created_at_iso"],
            message=d["message"],
            author=d["author"],
            components=list(d.get("components", [])),
            total_files=d.get("total_files", 0),
            total_bytes=d.get("total_bytes", 0),
            sha256=d.get("sha256", ""),
            zip_path=d.get("zip_path", ""),
        )


# --- motor principal ---

class LocalSnapshotEngine:
    """Motor de respaldos locales con compresión ZIP."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.backup_root = self.store_dir / "backups"
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self.chapter_planner = ChapterPlanner()
        self.snapshot_engine = get_snapshot_engine()
        self._lock = threading.RLock()

    def _work_backup_dir(self, work_id: str) -> Path:
        d = self.backup_root / f"work_{_safe_work_id(work_id)}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _index_path(self, work_id: str) -> Path:
        return self.backup_root / f"work_{_safe_work_id(work_id)}.backup_index.json"

    def _load_index(self, work_id: str) -> List[SnapshotManifest]:
        with self._lock:
            idx = self._index_path(work_id)
            if not idx.exists():
                return []
            try:
                data = json.loads(idx.read_text(encoding="utf-8"))
                return [SnapshotManifest.from_dict(m) for m in data.get("snapshots", [])]
            except Exception:
                return []

    def _save_index(self, work_id: str, snapshots: List[SnapshotManifest]) -> None:
        with self._lock:
            idx = self._index_path(work_id)
            tmp = idx.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"snapshots": [s.to_dict() for s in snapshots]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(idx)

    # --- recolección de componentes ---

    def _collect_work_meta(self, work_id: str) -> Optional[Dict[str, Any]]:
        work = self.storage.get_work(work_id)
        return work

    def _collect_characters(self, work_id: str) -> List[Dict[str, Any]]:
        return self.character_bible.list(work_id)

    def _collect_canon(self, work_id: str) -> List[Dict[str, Any]]:
        return self.canon_tracker.get_all_events(work_id)

    def _collect_chronology(self, work_id: str) -> Dict[str, Any]:
        return self.canon_tracker.get_chronology(work_id)

    def _collect_chapters(self, work_id: str) -> List[Dict[str, Any]]:
        return self.chapter_planner.list_chapters(work_id)

    def _collect_graph(self, work_id: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.story_memory.graph_manager import get_graph_manager
            gm = get_graph_manager()
            graph = gm.export_graph_data(work_id)
            if graph and graph.get("status") == "ok" and (graph.get("nodes") or graph.get("edges")):
                return graph
        except Exception:
            pass
        return None

    def _collect_timeline(self, work_id: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.story_memory.timeline_manager import get_timeline_manager
            tm = get_timeline_manager()
            timeline = tm.export_timeline(work_id)
            if timeline and timeline.get("status") == "ok" and (timeline.get("nodes") or timeline.get("edges")):
                return timeline
        except Exception:
            pass
        return None

    def _collect_gazetteer(self, work_id: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.story_memory.gazetteer import get_gazetteer
            gz = get_gazetteer()
            codex = gz.get_codex_stats(work_id)
            if codex and codex.get("status") == "ok" and codex.get("total", 0) > 0:
                return gz.export_codex(work_id)
        except Exception:
            pass
        return None

    def _collect_rag(self, work_id: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.story_memory.vector_rag import get_vector_engine
            ve = get_vector_engine()
            # El índice RAG es binario (base64), solo exportamos metadatos
            idx = ve.get_index_stats(work_id) if hasattr(ve, "get_index_stats") else None
            if idx:
                return idx
        except Exception:
            pass
        return None

    # --- snapshot principal ---

    def create_snapshot(
        self,
        work_id: str,
        message: str = "manual backup",
        author: str = "ame",
        components: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Crea una instantánea completa comprimida de la obra."""
        if not self.storage.work_exists(work_id):
            return {"status": "error", "error": "work_not_found", "work_id": work_id}

        # Componentes por defecto
        all_components = [
            "work_meta", "characters", "canon", "chronology",
            "chapters", "graph", "timeline", "gazetteer", "rag"
        ]
        selected = set(components) if components else set(all_components)

        ts = _now()
        snap_id = f"snap_{int(ts * 1000)}"
        work_dir = self._work_backup_dir(work_id)
        zip_name = f"{snap_id}.zip"
        zip_path = work_dir / zip_name

        collected: Dict[str, Any] = {}
        components_included: List[str] = []
        total_files = 0

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # work_meta
            if "work_meta" in selected:
                meta = self._collect_work_meta(work_id)
                if meta:
                    zf.writestr("work_meta.json", json.dumps(meta, ensure_ascii=False, indent=2, default=str))
                    components_included.append("work_meta")
                    total_files += 1

            # characters
            if "characters" in selected:
                chars = self._collect_characters(work_id)
                if chars:
                    zf.writestr("characters.json", json.dumps(chars, ensure_ascii=False, indent=2, default=str))
                    components_included.append("characters")
                    total_files += 1

            # canon
            if "canon" in selected:
                canon = self._collect_canon(work_id)
                if canon:
                    zf.writestr("canon.json", json.dumps(canon, ensure_ascii=False, indent=2, default=str))
                    components_included.append("canon")
                    total_files += 1

            # chronology
            if "chronology" in selected:
                chrono = self._collect_chronology(work_id)
                if chrono:
                    zf.writestr("chronology.json", json.dumps(chrono, ensure_ascii=False, indent=2, default=str))
                    components_included.append("chronology")
                    total_files += 1

            # chapters
            if "chapters" in selected:
                chaps = self._collect_chapters(work_id)
                if chaps:
                    zf.writestr("chapters.json", json.dumps(chaps, ensure_ascii=False, indent=2, default=str))
                    components_included.append("chapters")
                    total_files += 1

            # graph
            if "graph" in selected:
                graph = self._collect_graph(work_id)
                if graph:
                    zf.writestr("graph.json", json.dumps(graph, ensure_ascii=False, indent=2, default=str))
                    components_included.append("graph")
                    total_files += 1

            # timeline
            if "timeline" in selected:
                timeline = self._collect_timeline(work_id)
                if timeline:
                    zf.writestr("timeline.json", json.dumps(timeline, ensure_ascii=False, indent=2, default=str))
                    components_included.append("timeline")
                    total_files += 1

            # gazetteer
            if "gazetteer" in selected:
                gaz = self._collect_gazetteer(work_id)
                if gaz:
                    zf.writestr("gazetteer.json", json.dumps(gaz, ensure_ascii=False, indent=2, default=str))
                    components_included.append("gazetteer")
                    total_files += 1

            # rag
            if "rag" in selected:
                rag = self._collect_rag(work_id)
                if rag:
                    zf.writestr("rag_index.json", json.dumps(rag, ensure_ascii=False, indent=2, default=str))
                    components_included.append("rag")
                    total_files += 1

            # manifest del snapshot
            manifest = {
                "snapshot_id": snap_id,
                "work_id": work_id,
                "created_at": ts,
                "created_at_iso": _iso(ts),
                "message": message,
                "author": author,
                "components": components_included,
            }
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # Hash y tamaño
        sha256 = _sha256_file(zip_path)
        total_bytes = zip_path.stat().st_size

        # Actualizar índice
        snap_manifest = SnapshotManifest(
            snapshot_id=snap_id,
            work_id=work_id,
            created_at=ts,
            created_at_iso=_iso(ts),
            message=message,
            author=author,
            components=components_included,
            total_files=total_files + 1,  # + manifest
            total_bytes=total_bytes,
            sha256=sha256,
            zip_path=str(zip_path.relative_to(self.store_dir)),
        )
        snapshots = self._load_index(work_id)
        snapshots.append(snap_manifest)
        self._save_index(work_id, snapshots)

        return {"status": "created", "snapshot": snap_manifest.to_dict()}

    def list_snapshots(self, work_id: str) -> Dict[str, Any]:
        """Lista todas las instantáneas de una obra."""
        snapshots = self._load_index(work_id)
        return {
            "status": "ok",
            "work_id": work_id,
            "count": len(snapshots),
            "snapshots": [s.to_dict() for s in snapshots],
        }

    def get_snapshot(self, work_id: str, snapshot_id: str) -> Dict[str, Any]:
        """Obtiene metadatos de una instantánea."""
        snapshots = self._load_index(work_id)
        for s in snapshots:
            if s.snapshot_id == snapshot_id:
                return {"status": "ok", "work_id": work_id, "snapshot": s.to_dict()}
        return {"status": "error", "error": "snapshot_not_found"}

    def restore_snapshot(
        self,
        work_id: str,
        snapshot_id: str,
        target_work_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restaura una obra desde una instantánea (crea work_id destino si no existe)."""
        snapshots = self._load_index(work_id)
        snap = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
        if not snap:
            return {"status": "error", "error": "snapshot_not_found"}

        zip_path = self.store_dir / snap.zip_path
        if not zip_path.exists():
            return {"status": "error", "error": "zip_file_missing"}

        target = target_work_id or f"{work_id}_restored_{int(_now())}"
        
        # Extraer ZIP a directorio temporal
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            
            tmp_path = Path(tmpdir)
            
            # Crear work destino si no existe
            if not self.storage.work_exists(target):
                work_meta_path = tmp_path / "work_meta.json"
                if work_meta_path.exists():
                    meta = json.loads(work_meta_path.read_text(encoding="utf-8"))
                    meta["work_id"] = target
                    meta["title"] = meta.get("title", "") + " (restored)"
                    # Use create_work which ensures directory structure
                    self.storage.create_work(
                        work_id=target,
                        title=meta.get("title", ""),
                        universe=meta.get("universe", ""),
                        description=meta.get("description", ""),
                        author=meta.get("author", "")
                    )
                    # Update with original metadata
                    self.storage._save_json(self.storage._meta_path(target), meta)
                else:
                    self.storage.create_work(work_id=target, title=f"Restored {work_id}", universe="", description="", author="")

            # Restaurar cada componente
            restored = []
            
            if (tmp_path / "characters.json").exists():
                chars = json.loads((tmp_path / "characters.json").read_text(encoding="utf-8"))
                for c in chars:
                    c["char_id"] = c.get("char_id", "")
                    self.character_bible.storage.save_character(target, c["char_id"], c)
                restored.append("characters")

            if (tmp_path / "canon.json").exists():
                canon = json.loads((tmp_path / "canon.json").read_text(encoding="utf-8"))
                for e in canon:
                    # Use CanonTracker to properly restore canon/continuity events
                    certainty = e.get("certainty", "canon")
                    if certainty == "canon":
                        self.canon_tracker.add_canon_event(
                            target,
                            description=e.get("description", ""),
                            timestamp=e.get("timestamp", 0),
                            scene_ref=e.get("scene_ref", ""),
                            source=e.get("source", "restored"),
                        )
                    else:
                        self.canon_tracker.add_continuity_event(
                            target,
                            description=e.get("description", ""),
                            timestamp=e.get("timestamp", 0),
                            scene_ref=e.get("scene_ref", ""),
                            source=e.get("source", "restored"),
                        )
                restored.append("canon")

            if (tmp_path / "chapters.json").exists():
                chaps = json.loads((tmp_path / "chapters.json").read_text(encoding="utf-8"))
                for ch in chaps:
                    self.chapter_planner.storage.save_chapter(target, ch)
                restored.append("chapters")

            # graph, timeline, gazetteer se restauran via sus managers si están disponibles
            if (tmp_path / "graph.json").exists():
                try:
                    from backend.story_memory.graph_manager import get_graph_manager
                    gm = get_graph_manager()
                    graph_data = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
                    gm.import_graph(target, graph_data)
                    restored.append("graph")
                except Exception:
                    pass

            if (tmp_path / "timeline.json").exists():
                try:
                    from backend.story_memory.timeline_manager import get_timeline_manager
                    tm = get_timeline_manager()
                    tl_data = json.loads((tmp_path / "timeline.json").read_text(encoding="utf-8"))
                    tm.import_timeline(target, tl_data)
                    restored.append("timeline")
                except Exception:
                    pass

            if (tmp_path / "gazetteer.json").exists():
                try:
                    from backend.story_memory.gazetteer import get_gazetteer
                    gz = get_gazetteer()
                    gz_data = json.loads((tmp_path / "gazetteer.json").read_text(encoding="utf-8"))
                    gz.import_codex(target, gz_data)
                    restored.append("gazetteer")
                except Exception:
                    pass

            if (tmp_path / "rag_index.json").exists():
                try:
                    from backend.story_memory.vector_rag import get_vector_engine
                    ve = get_vector_engine()
                    ve.import_index(target, json.loads((tmp_path / "rag_index.json").read_text(encoding="utf-8")))
                    restored.append("rag")
                except Exception:
                    pass

        return {
            "status": "restored",
            "source_work_id": work_id,
            "target_work_id": target,
            "snapshot_id": snapshot_id,
            "restored_components": restored,
        }

    def delete_snapshot(self, work_id: str, snapshot_id: str) -> Dict[str, Any]:
        """Elimina una instantánea (archivo ZIP + entrada en índice)."""
        snapshots = self._load_index(work_id)
        snap = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
        if not snap:
            return {"status": "error", "error": "snapshot_not_found"}

        zip_path = self.store_dir / snap.zip_path
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass

        snapshots = [s for s in snapshots if s.snapshot_id != snapshot_id]
        self._save_index(work_id, snapshots)

        return {"status": "deleted", "work_id": work_id, "snapshot_id": snapshot_id}

    def cleanup_old(self, work_id: str, keep: int = 10, max_age_days: int = 30) -> int:
        """Limpia instantáneas antiguas (mantiene como máximo 'keep' más recientes y elimina > max_age_days)."""
        snapshots = self._load_index(work_id)
        now = _now()
        max_age = max_age_days * 86400
        removed = 0
        
        # Ordenar por fecha (más reciente primero)
        snapshots_sorted = sorted(snapshots, key=lambda x: x.created_at, reverse=True)
        
        # Mantener las 'keep' más recientes siempre (límite duro de cantidad)
        keep_set = {s.snapshot_id for s in snapshots_sorted[:keep]}
        
        # Candidatos a eliminar: los que exceden el límite keep
        to_delete = []
        for s in snapshots_sorted[keep:]:
            to_delete.append(s)
        
        # Además, eliminar cualquier snapshot (incluso dentro de keep) que supere max_age_days
        # excepto si max_age_days == 0 (sin límite de edad)
        if max_age_days > 0:
            for s in snapshots_sorted[keep:]:
                if s.snapshot_id in keep_set:
                    continue
                # Ya está en to_delete por exceder keep
            # Verificar los que están en keep_set pero son muy antiguos
            for s in snapshots_sorted[:keep]:
                if now - s.created_at > max_age:
                    to_delete.append(s)
        elif max_age_days == 0:
            # Sin límite de edad, solo aplica el límite keep (ya hecho arriba)
            pass
        
        # Eliminar duplicados en to_delete
        to_delete_unique = []
        seen = set()
        for s in to_delete:
            if s.snapshot_id not in seen:
                seen.add(s.snapshot_id)
                to_delete_unique.append(s)
        
        for s in to_delete_unique:
            zip_path = self.store_dir / s.zip_path
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
            snapshots = [x for x in snapshots if x.snapshot_id != s.snapshot_id]
            removed += 1
        
        if removed:
            self._save_index(work_id, snapshots)
        return removed


# --- singleton ---

_engine: Optional[LocalSnapshotEngine] = None
_engine_lock = threading.Lock()


def get_backup_engine(store_dir: Optional[str] = None) -> LocalSnapshotEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = LocalSnapshotEngine(store_dir=store_dir)
    return _engine


def reset_backup_engine() -> None:
    global _engine
    with _engine_lock:
        _engine = None