"""Literary Snapshot Engine — control de versiones liviano (Git-lite) para la base literaria.

Permite:
1. Congelar el estado de una obra (metadata + characters + canon + chapters) en un snapshot.
2. Aislar bifurcaciones narrativas (branches) sin tocar el canon principal.
3. Calcular un hash de estado del canon para detectar cambios entre snapshots.
4. Exportar snapshots como paquetes JSON para respaldo en Discord Vault.

Almacenamiento: ficheros JSON en `<store_dir>/versions/<work_id>/`.
Cada snapshot es un directorio con:
  - manifest.json  (commit message, timestamp, author, canon_hash, branch)
  - data.json      (snapshot serializado de la obra)

No introduce dependencias externas ni bases de datos. Usa hashlib estándar.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner


class LiterarySnapshotEngine:
    """Motor de versiones literarias con snapshots y ramificaciones narrativas."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.storage = StoryStorage(store_dir)
        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self.chapter_planner = ChapterPlanner()
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self._versions_dir = self.store_dir / "versions"
        self._lock = threading.Lock()

    def _work_versions_dir(self, work_id: str) -> Path:
        return self._versions_dir / f"work_{work_id}"

    def _snapshots_dir(self, work_id: str, branch: str = "main") -> Path:
        sanitized = "".join(c for c in branch if c.isalnum() or c in ("-", "_")) or "main"
        return self._work_versions_dir(work_id) / sanitized

    def _canon_state_hash(self, work_id: str) -> str:
        """Hash SHA-256 del estado actual del canon + continuidad de una obra."""
        events = self.canon_tracker.get_all_events(work_id)
        raw = json.dumps(events, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _serialize_work(self, work_id: str) -> Dict[str, Any]:
        """Serializa el estado completo de una obra para snapshot."""
        work = self.storage.get_work(work_id)
        return {
            "work": work,
            "characters": self.character_bible.list(work_id),
            "canon": self.canon_tracker.get_all_events(work_id),
            "chronology": self.canon_tracker.get_chronology(work_id),
            "chapters": self.chapter_planner.list_chapters(work_id),
            "canon_hash": self._canon_state_hash(work_id),
        }

    def create_snapshot(
        self,
        work_id: str,
        message: str = "checkpoint",
        author: str = "ame",
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Crea un snapshot del estado actual de una obra.

        Retorna el manifest del snapshot con su ID y hash.
        """
        with self._lock:
            if not self.storage.work_exists(work_id):
                return {"status": "error", "error": "work_not_found", "work_id": work_id}

            snap_dir = self._snapshots_dir(work_id, branch)
            snap_dir.mkdir(parents=True, exist_ok=True)

            ts = time.time()
            snap_id = f"snap_{int(ts * 1000)}"
            data = self._serialize_work(work_id)
            canon_hash = data["canon_hash"]

            (snap_dir / f"{snap_id}_data.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

            manifest = {
                "snapshot_id": snap_id,
                "work_id": work_id,
                "branch": branch,
                "created_at": ts,
                "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
                "message": message,
                "author": author,
                "canon_hash": canon_hash,
                "parent": self._latest_snapshot_id(work_id, branch) if branch == "main" else None,
            }

            manifest_path = snap_dir / f"{snap_id}_manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            return {"status": "created", "snapshot": manifest}

    def _latest_snapshot_id(self, work_id: str, branch: str = "main") -> Optional[str]:
        snap_dir = self._snapshots_dir(work_id, branch)
        if not snap_dir.exists():
            return None
        manifests = sorted(snap_dir.glob("*_manifest.json"))
        if not manifests:
            return None
        try:
            data = json.loads(manifests[-1].read_text(encoding="utf-8"))
            return data.get("snapshot_id")
        except (json.JSONDecodeError, OSError):
            return None

    def list_snapshots(self, work_id: str, branch: str = "main") -> List[Dict[str, Any]]:
        """Lista todos los snapshots de una obra (y rama)."""
        snap_dir = self._snapshots_dir(work_id, branch)
        if not snap_dir.exists():
            return []
        results: List[Dict[str, Any]] = []
        for p in sorted(snap_dir.glob("*_manifest.json")):
            try:
                results.append(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def list_branches(self, work_id: str) -> List[str]:
        """Lista las ramas narrativas disponibles para una obra."""
        work_ver = self._work_versions_dir(work_id)
        if not work_ver.exists():
            return ["main"]
        branches = ["main"]
        for d in work_ver.iterdir():
            if d.is_dir() and d.name not in ("main",) and not d.name.startswith("work_"):
                branches.append(d.name)
        return branches

    def get_snapshot(self, work_id: str, snapshot_id: str, branch: str = "main") -> Optional[Dict[str, Any]]:
        """Recupera un snapshot por ID."""
        snap_dir = self._snapshots_dir(work_id, branch)
        manifest_path = snap_dir / f"{snapshot_id}_manifest.json"
        data_path = snap_dir / f"{snapshot_id}_data.json"
        if not manifest_path.exists() or not data_path.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            data = json.loads(data_path.read_text(encoding="utf-8"))
            return {"manifest": manifest, "data": data}
        except (json.JSONDecodeError, OSError):
            return None

    def restore_snapshot(self, work_id: str, snapshot_id: str, branch: str = "main") -> Dict[str, Any]:
        """Restaura el estado de una obra desde un snapshot (destructivo sobre el work)."""
        with self._lock:
            snap = self.get_snapshot(work_id, snapshot_id, branch)
            if not snap:
                return {"status": "error", "error": "snapshot_not_found"}

            new_branch = f"restored_{int(time.time())}"
            self._create_branch_from_snapshot(work_id, new_branch, snap["data"])

            work_data = snap["data"]
            work = work_data.get("work", {})
            if work:
                self.storage._save_json(self.storage._meta_path(work_id), work)

            return {
                "status": "restored",
                "work_id": work_id,
                "snapshot_id": snapshot_id,
                "restored_to_branch": new_branch,
            }

    def _create_branch_from_snapshot(self, work_id: str, branch: str, data: Dict[str, Any]) -> None:
        """Crea una rama narrativa a partir de un snapshot serializado."""
        snap_dir = self._snapshots_dir(work_id, branch)
        snap_dir.mkdir(parents=True, exist_ok=True)
        ts = time.time()
        snap_id = f"snap_{int(ts * 1000)}"
        (snap_dir / f"{snap_id}_data.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        manifest = {
            "snapshot_id": snap_id,
            "work_id": work_id,
            "branch": branch,
            "created_at": ts,
            "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts)),
            "message": "branch from restore",
            "author": "system",
            "canon_hash": data.get("canon_hash", ""),
            "parent": None,
        }
        manifest_path = snap_dir / f"{snap_id}_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def diff_snapshots(
        self,
        work_id: str,
        snapshot_a: str,
        snapshot_b: str,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Calcula el diff entre dos snapshots de una obra."""
        snap_a = self.get_snapshot(work_id, snapshot_a, branch)
        snap_b = self.get_snapshot(work_id, snapshot_b, branch)
        if not snap_a or not snap_b:
            return {"status": "error", "error": "one or both snapshots not found"}

        data_a = snap_a["data"]
        data_b = snap_b["data"]

        canon_a = {e.get("event_id"): e for e in data_a.get("canon", [])}
        canon_b = {e.get("event_id"): e for e in data_b.get("canon", [])}
        all_ids = set(canon_a.keys()) | set(canon_b.keys())

        added = [eid for eid in all_ids if eid not in canon_a]
        removed = [eid for eid in all_ids if eid not in canon_b]
        modified = [
            eid for eid in all_ids
            if eid in canon_a and eid in canon_b and canon_a[eid] != canon_b[eid]
        ]

        chars_a = {c.get("char_id"): c for c in data_a.get("characters", [])}
        chars_b = {c.get("char_id"): c for c in data_b.get("characters", [])}
        all_chars = set(chars_a.keys()) | set(chars_b.keys())
        char_changes = []
        for cid in all_chars:
            if cid not in chars_a:
                char_changes.append({"char_id": cid, "change": "added"})
            elif cid not in chars_b:
                char_changes.append({"char_id": cid, "change": "removed"})
            elif chars_a[cid] != chars_b[cid]:
                char_changes.append({"char_id": cid, "change": "modified"})

        return {
            "status": "ok",
            "work_id": work_id,
            "snapshot_a": snapshot_a,
            "snapshot_b": snapshot_b,
            "canon_diff": {"added": added, "removed": removed, "modified": modified},
            "character_diff": char_changes,
            "canon_hash_a": data_a.get("canon_hash", ""),
            "canon_hash_b": data_b.get("canon_hash", ""),
            "changed": bool(added or removed or modified or char_changes),
        }

    def export_snapshot(self, work_id: str, snapshot_id: str, branch: str = "main") -> Optional[str]:
        """Exporta un snapshot como JSON serializable para respaldo en Discord Vault."""
        snap = self.get_snapshot(work_id, snapshot_id, branch)
        if not snap:
            return None
        return json.dumps(snap, indent=2, ensure_ascii=False, default=str)


_engine: Optional["LiterarySnapshotEngine"] = None
_lock_init = threading.Lock()


def get_snapshot_engine() -> LiterarySnapshotEngine:
    global _engine
    if _engine is None:
        with _lock_init:
            if _engine is None:
                _engine = LiterarySnapshotEngine()
    return _engine


def set_engine_store_path(path: str) -> None:
    """Override del path de almacenamiento (para testing)."""
    global _engine
    with _lock_init:
        _engine = LiterarySnapshotEngine(store_dir=path)
