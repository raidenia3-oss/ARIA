"""AURA P2P Offline Sync & Conflict Resolution Engine (BLOQUE 50).

Motor de sincronización peer-to-peer y resolución de conflictos para
AURA PC ↔ AME Mobile (tarjeta SD).

Funcionalidades:
- Comparación de hashes de versión para detección de divergencias
- Estrategias de resolución: LWW (last-write-wins), merge de metadatos, backup automático
- Payloads diferenciales para WebSocket local
- Endpoints REST y eventos WebSocket para conciliación de estados
- Persistencia de estado de sync en disco (sin dependencias cloud)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.story_storage import StoryStorage
from backend.websocket_manager import ws_gateway

router = APIRouter(prefix="/api/sync", tags=["p2p_sync"])

SYNC_DIR_ENV = "AURA_SYNC_DIR"
STATE_FILE = "p2p_sync_state.json"
CONFLICT_LOG_FILE = "p2p_conflict_log.json"
MAX_CONFLICT_LOG = 5000
_device_sessions: Dict[str, Dict[str, Any]] = {}
_device_locks: Dict[str, threading.Lock] = {}
_global_lock = threading.Lock()


def _sync_dir() -> Path:
    return Path(os.getenv(SYNC_DIR_ENV, os.path.join(os.getcwd(), "data")))


def _state_path() -> Path:
    return _sync_dir() / STATE_FILE


def _conflict_log_path() -> Path:
    return _sync_dir() / CONFLICT_LOG_FILE


def _ensure_dirs() -> None:
    _sync_dir().mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _get_device_lock(device_id: str) -> threading.Lock:
    with _global_lock:
        if device_id not in _device_locks:
            _device_locks[device_id] = threading.Lock()
        return _device_locks[device_id]


def _compute_hash(data: Any) -> str:
    """Compute SHA256 hash of JSON-serializable data."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class DocumentVersion:
    """Version metadata for a synced document."""
    doc_type: str
    doc_id: str
    work_id: str
    version_hash: str
    version_vector: Dict[str, int] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now_iso)
    updated_by: str = "unknown"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "doc_id": self.doc_id,
            "work_id": self.work_id,
            "version_hash": self.version_hash,
            "version_vector": self.version_vector,
            "updated_at": self.updated_at,
            "updated_by": self.updated_by,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentVersion":
        return cls(
            doc_type=data["doc_type"],
            doc_id=data["doc_id"],
            work_id=data["work_id"],
            version_hash=data["version_hash"],
            version_vector=data.get("version_vector", {}),
            updated_at=data.get("updated_at", _now_iso()),
            updated_by=data.get("updated_by", "unknown"),
            payload=data.get("payload", {}),
        )


@dataclass
class ConflictRecord:
    """Record of a detected conflict during sync."""
    conflict_id: str
    work_id: str
    doc_type: str
    doc_id: str
    pc_version: DocumentVersion
    mobile_version: DocumentVersion
    resolution_strategy: str
    resolved_version: Optional[DocumentVersion] = None
    auto_backup_created: bool = False
    created_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "work_id": self.work_id,
            "doc_type": self.doc_type,
            "doc_id": self.doc_id,
            "pc_version": self.pc_version.to_dict(),
            "mobile_version": self.mobile_version.to_dict(),
            "resolution_strategy": self.resolution_strategy,
            "resolved_version": self.resolved_version.to_dict() if self.resolved_version else None,
            "auto_backup_created": self.auto_backup_created,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


class P2PSyncEngine:
    """Motor principal de sincronización P2P con resolución de conflictos."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.sync_dir = _sync_dir()
        _ensure_dirs()
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self.chapter_planner = ChapterPlanner()
        self._lock = threading.RLock()

        self._state = _load_json(_state_path(), {
            "devices": {},
            "document_versions": {},
            "last_global_sync": None,
            "total_conflicts": 0,
        })
        self._conflict_log: List[Dict[str, Any]] = _load_json(_conflict_log_path(), [])

    def _persist_state(self) -> None:
        _save_json(_state_path(), self._state)

    def _persist_conflict_log(self) -> None:
        if len(self._conflict_log) > MAX_CONFLICT_LOG:
            self._conflict_log = self._conflict_log[-MAX_CONFLICT_LOG:]
        _save_json(_conflict_log_path(), self._conflict_log)

    def _get_doc_key(self, work_id: str, doc_type: str, doc_id: str) -> str:
        return f"{work_id}:{doc_type}:{doc_id}"

    def _load_current_version(self, work_id: str, doc_type: str, doc_id: str) -> Optional[DocumentVersion]:
        """Load current version from local storage."""
        try:
            if doc_type == "character":
                char = self.character_bible.get(work_id, doc_id)
                if char:
                    return DocumentVersion(
                        doc_type="character",
                        doc_id=doc_id,
                        work_id=work_id,
                        version_hash=_compute_hash(char),
                        version_vector={"pc": char.get("updated_at", 0)},
                        updated_at=str(char.get("updated_at", "")),
                        updated_by="pc",
                        payload=char,
                    )
            elif doc_type == "canon":
                events = self.canon_tracker.get_canon_events(work_id)
                event = next((e for e in events if e.get("event_id") == doc_id), None)
                if event:
                    return DocumentVersion(
                        doc_type="canon",
                        doc_id=doc_id,
                        work_id=work_id,
                        version_hash=_compute_hash(event),
                        version_vector={"pc": event.get("updated_at", 0)},
                        updated_at=str(event.get("updated_at", "")),
                        updated_by="pc",
                        payload=event,
                    )
            elif doc_type == "continuity":
                events = self.canon_tracker.get_continuity_events(work_id)
                event = next((e for e in events if e.get("event_id") == doc_id), None)
                if event:
                    return DocumentVersion(
                        doc_type="continuity",
                        doc_id=doc_id,
                        work_id=work_id,
                        version_hash=_compute_hash(event),
                        version_vector={"pc": event.get("updated_at", 0)},
                        updated_at=str(event.get("updated_at", "")),
                        updated_by="pc",
                        payload=event,
                    )
            elif doc_type == "chapter":
                chapter = self.chapter_planner.get_chapter(work_id, doc_id)
                if chapter:
                    return DocumentVersion(
                        doc_type="chapter",
                        doc_id=doc_id,
                        work_id=work_id,
                        version_hash=_compute_hash(chapter),
                        version_vector={"pc": chapter.get("updated_at", 0)},
                        updated_at=str(chapter.get("updated_at", "")),
                        updated_by="pc",
                        payload=chapter,
                    )
        except Exception:
            pass
        return None

    def register_device(self, device_id: str, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Register a mobile device for sync."""
        with self._lock:
            device_lock = _get_device_lock(device_id)
            with device_lock:
                self._state["devices"][device_id] = {
                    "device_id": device_id,
                    "name": device_info.get("name", device_id),
                    "platform": device_info.get("platform", "unknown"),
                    "last_sync": device_info.get("last_sync"),
                    "version_vector": device_info.get("version_vector", {}),
                    "capabilities": device_info.get("capabilities", []),
                    "status": "connected",
                    "registered_at": _now_iso(),
                }
                self._persist_state()
        return {"status": "registered", "device_id": device_id}

    def get_device_state(self, device_id: str) -> Dict[str, Any]:
        with self._lock:
            device = self._state["devices"].get(device_id)
            if not device:
                return {"status": "not_found", "device_id": device_id}
            return {"status": "ok", "device": device}

    def list_devices(self) -> Dict[str, Any]:
        with self._lock:
            return {"status": "ok", "devices": list(self._state["devices"].values())}

    def compare_versions(
        self,
        device_id: str,
        work_id: str,
        doc_type: str,
        doc_id: str,
        mobile_hash: str,
        mobile_version_vector: Dict[str, int],
    ) -> Dict[str, Any]:
        """Compare PC version with mobile version to detect conflicts."""
        pc_version = self._load_current_version(work_id, doc_type, doc_id)
        if not pc_version:
            return {
                "status": "not_found_local",
                "action": "push_mobile",
                "doc_type": doc_type,
                "doc_id": doc_id,
            }

        if pc_version.version_hash == mobile_hash:
            return {
                "status": "in_sync",
                "doc_type": doc_type,
                "doc_id": doc_id,
                "version_hash": pc_version.version_hash,
            }

        mobile_version = DocumentVersion(
            doc_type=doc_type,
            doc_id=doc_id,
            work_id=work_id,
            version_hash=mobile_hash,
            version_vector=mobile_version_vector,
            updated_at=_now_iso(),
            updated_by=device_id,
        )

        return {
            "status": "conflict",
            "doc_type": doc_type,
            "doc_id": doc_id,
            "pc_version": pc_version.to_dict(),
            "mobile_version": mobile_version.to_dict(),
            "resolution_options": ["lww_pc", "lww_mobile", "merge", "manual"],
        }

    def resolve_conflict(
        self,
        work_id: str,
        doc_type: str,
        doc_id: str,
        mobile_payload: Dict[str, Any],
        mobile_hash: str,
        mobile_version_vector: Dict[str, int],
        strategy: str = "lww_mobile",
        device_id: str = "mobile",
    ) -> Dict[str, Any]:
        """Resolve a conflict using specified strategy."""
        pc_version = self._load_current_version(work_id, doc_type, doc_id)
        if not pc_version:
            return {"status": "error", "error": "document_not_found_on_pc"}

        mobile_version = DocumentVersion(
            doc_type=doc_type,
            doc_id=doc_id,
            work_id=work_id,
            version_hash=mobile_hash,
            version_vector=mobile_version_vector,
            updated_at=_now_iso(),
            updated_by=device_id,
            payload=mobile_payload,
        )

        conflict = ConflictRecord(
            conflict_id=str(uuid.uuid4())[:12],
            work_id=work_id,
            doc_type=doc_type,
            doc_id=doc_id,
            pc_version=pc_version,
            mobile_version=mobile_version,
            resolution_strategy=strategy,
        )

        resolved = None
        backup_created = False

        if strategy == "lww_pc":
            resolved = pc_version
        elif strategy == "lww_mobile":
            resolved = mobile_version
            self._apply_to_storage(work_id, doc_type, doc_id, mobile_payload)
        elif strategy == "merge":
            resolved = self._merge_versions(pc_version, mobile_version, doc_type)
            self._apply_to_storage(work_id, doc_type, doc_id, resolved.payload)
        elif strategy == "backup_both":
            resolved = pc_version
            backup_created = self._create_conflict_backup(work_id, doc_type, doc_id, pc_version, mobile_version)
        else:
            return {"status": "error", "error": f"unknown_strategy: {strategy}"}

        conflict.resolved_version = resolved
        conflict.auto_backup_created = backup_created
        conflict.resolved_at = _now_iso()

        self._conflict_log.append(conflict.to_dict())
        self._persist_conflict_log()
        self._state["total_conflicts"] += 1
        self._persist_state()

        key = self._get_doc_key(work_id, doc_type, doc_id)
        self._state["document_versions"][key] = resolved.to_dict()
        self._persist_state()

        return {
            "status": "resolved",
            "conflict": conflict.to_dict(),
            "resolved_version": resolved.to_dict() if resolved else None,
        }

    def _merge_versions(self, pc: DocumentVersion, mobile: DocumentVersion, doc_type: str) -> DocumentVersion:
        """Merge two versions (metadata merge, LWW for content)."""
        pc_payload = pc.payload.copy()
        mobile_payload = mobile.payload.copy()

        merged = pc_payload.copy()

        for key, mobile_val in mobile_payload.items():
            pc_val = pc_payload.get(key)
            if isinstance(pc_val, dict) and isinstance(mobile_val, dict):
                merged[key] = {**pc_val, **mobile_val}
            elif isinstance(pc_val, list) and isinstance(mobile_val, list):
                merged[key] = list(dict.fromkeys(pc_val + mobile_val))
            else:
                mobile_ts = mobile.version_vector.get("mobile", 0)
                pc_ts = pc.version_vector.get("pc", 0)
                merged[key] = mobile_val if mobile_ts >= pc_ts else pc_val

        merged_version_vector = pc.version_vector.copy()
        for k, v in mobile.version_vector.items():
            merged_version_vector[k] = max(merged_version_vector.get(k, 0), v)

        return DocumentVersion(
            doc_type=doc_type,
            doc_id=pc.doc_id,
            work_id=pc.work_id,
            version_hash=_compute_hash(merged),
            version_vector=merged_version_vector,
            updated_at=_now_iso(),
            updated_by="merged",
            payload=merged,
        )

    def _apply_to_storage(self, work_id: str, doc_type: str, doc_id: str, payload: Dict[str, Any]) -> None:
        """Apply resolved payload to local storage."""
        if doc_type == "character":
            self.character_bible.update(work_id, doc_id, payload)
        elif doc_type == "canon":
            self.canon_tracker.add_canon_event(
                work_id=work_id,
                description=payload.get("description", ""),
                timestamp=payload.get("timestamp", time.time()),
                scene_ref=payload.get("scene_ref", f"sync:{doc_id}"),
                source=payload.get("source", "sync"),
            )
        elif doc_type == "continuity":
            self.canon_tracker.add_continuity_event(
                work_id=work_id,
                description=payload.get("description", ""),
                timestamp=payload.get("timestamp", time.time()),
                scene_ref=payload.get("scene_ref", f"sync:{doc_id}"),
                source=payload.get("source", "sync"),
            )
        elif doc_type == "chapter":
            self.chapter_planner.storage.save_chapter(work_id, {**payload, "chapter_id": doc_id})

    def _create_conflict_backup(
        self,
        work_id: str,
        doc_type: str,
        doc_id: str,
        pc_version: DocumentVersion,
        mobile_version: DocumentVersion,
    ) -> bool:
        """Create automatic backup of both conflicting versions."""
        try:
            backup_dir = self.sync_dir / "conflict_backups" / work_id / doc_type
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pc_backup = backup_dir / f"{doc_id}_pc_{timestamp}.json"
            mobile_backup = backup_dir / f"{doc_id}_mobile_{timestamp}.json"
            _save_json(pc_backup, pc_version.to_dict())
            _save_json(mobile_backup, mobile_version.to_dict())
            return True
        except Exception:
            return False

    def get_conflict_log(self, work_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """Get conflict resolution log."""
        with self._lock:
            log = self._conflict_log
            if work_id:
                log = [c for c in log if c.get("work_id") == work_id]
            return {"status": "ok", "conflicts": log[-limit:]}

    def get_sync_status(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Get overall sync status."""
        with self._lock:
            status = {
                "status": "ok",
                "devices": self._state.get("devices", {}),
                "total_documents": len(self._state.get("document_versions", {})),
                "total_conflicts": self._state.get("total_conflicts", 0),
                "last_global_sync": self._state.get("last_global_sync"),
            }
            if device_id:
                device = self._state["devices"].get(device_id)
                if device:
                    status["device"] = device
            return status

    def compute_differential_payload(
        self,
        device_id: str,
        work_id: str,
        since_version_vector: Dict[str, int],
    ) -> Dict[str, Any]:
        """Compute differential payload for sync (documents changed since version vector)."""
        doc_versions = self._state.get("document_versions", {})
        changes: List[Dict[str, Any]] = []

        for key, doc in doc_versions.items():
            if not key.startswith(f"{work_id}:"):
                continue
            doc_vector = doc.get("version_vector", {})
            needs_sync = False
            for k, v in doc_vector.items():
                if v > since_version_vector.get(k, 0):
                    needs_sync = True
                    break

            if needs_sync:
                changes.append(doc)

        return {
            "status": "ok",
            "device_id": device_id,
            "work_id": work_id,
            "changes": changes,
            "since_vector": since_version_vector,
            "computed_at": _now_iso(),
        }

    def ack_sync(self, device_id: str, work_id: str, applied_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Acknowledge applied changes from mobile device."""
        with self._lock:
            device = self._state["devices"].get(device_id)
            if device:
                device["last_sync"] = _now_iso()
                for change in applied_changes:
                    key = self._get_doc_key(work_id, change["doc_type"], change["doc_id"])
                    self._state["document_versions"][key] = change
                device["version_vector"] = {
                    **device.get("version_vector", {}),
                    "mobile": time.time(),
                }
                self._persist_state()

            self._state["last_global_sync"] = _now_iso()
            self._persist_state()

        return {"status": "acknowledged", "applied": len(applied_changes)}


# Global singleton
_engine: Optional[P2PSyncEngine] = None
_engine_lock = threading.Lock()


def get_p2p_sync_engine(store_dir: Optional[str] = None) -> P2PSyncEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = P2PSyncEngine(store_dir=store_dir)
    return _engine


def reset_p2p_sync_engine() -> None:
    global _engine
    with _engine_lock:
        _engine = None


# --- REST Endpoints ---

class RegisterDeviceRequest(BaseModel):
    device_id: str
    name: Optional[str] = None
    platform: Optional[str] = None
    capabilities: List[str] = []


@router.post("/register")
async def register_device(request: RegisterDeviceRequest) -> Dict[str, Any]:
    """Register a mobile device for P2P sync."""
    engine = get_p2p_sync_engine()
    payload = {
        "name": request.name or request.device_id,
        "platform": request.platform or "mobile",
        "capabilities": request.capabilities,
    }
    return engine.register_device(request.device_id, payload)


@router.get("/devices")
async def list_devices() -> Dict[str, Any]:
    """List registered devices."""
    engine = get_p2p_sync_engine()
    return engine.list_devices()


@router.get("/devices/{device_id}")
async def get_device(device_id: str) -> Dict[str, Any]:
    """Get device state."""
    engine = get_p2p_sync_engine()
    return engine.get_device_state(device_id)


@router.post("/compare")
async def compare_versions(
    device_id: str,
    work_id: str,
    doc_type: str,
    doc_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare PC version with mobile version."""
    engine = get_p2p_sync_engine()
    return engine.compare_versions(
        device_id=device_id,
        work_id=work_id,
        doc_type=doc_type,
        doc_id=doc_id,
        mobile_hash=payload.get("mobile_hash", ""),
        mobile_version_vector=payload.get("mobile_version_vector", {}),
    )


@router.post("/resolve")
async def resolve_conflict(
    device_id: str,
    work_id: str,
    doc_type: str,
    doc_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve a detected conflict."""
    engine = get_p2p_sync_engine()
    return engine.resolve_conflict(
        work_id=work_id,
        doc_type=doc_type,
        doc_id=doc_id,
        mobile_payload=payload.get("mobile_payload", {}),
        mobile_hash=payload.get("mobile_hash", ""),
        mobile_version_vector=payload.get("mobile_version_vector", {}),
        strategy=payload.get("strategy", "lww_mobile"),
        device_id=device_id,
    )


@router.get("/conflicts")
async def get_conflicts(work_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Get conflict resolution log."""
    engine = get_p2p_sync_engine()
    return engine.get_conflict_log(work_id, limit)


@router.get("/status")
async def sync_status(device_id: Optional[str] = None) -> Dict[str, Any]:
    """Get sync engine status."""
    engine = get_p2p_sync_engine()
    return engine.get_sync_status(device_id)


@router.post("/differential")
async def differential_payload(
    device_id: str,
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Get differential payload for sync."""
    engine = get_p2p_sync_engine()
    return engine.compute_differential_payload(
        device_id=device_id,
        work_id=work_id,
        since_version_vector=payload.get("since_version_vector", {}),
    )


@router.post("/ack")
async def ack_sync(
    device_id: str,
    work_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Acknowledge applied changes."""
    engine = get_p2p_sync_engine()
    return engine.ack_sync(
        device_id=device_id,
        work_id=work_id,
        applied_changes=payload.get("applied_changes", []),
    )


@router.post("/reconcile")
async def full_reconcile(device_id: str, work_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Full reconciliation: compare all documents and return conflicts + resolutions."""
    engine = get_p2p_sync_engine()
    mobile_versions = payload.get("versions", [])
    conflicts = []
    synced = 0

    for mv in mobile_versions:
        doc_type = mv.get("doc_type")
        doc_id = mv.get("doc_id")
        if not doc_type or not doc_id:
            continue

        result = engine.compare_versions(
            device_id=device_id,
            work_id=work_id,
            doc_type=doc_type,
            doc_id=doc_id,
            mobile_hash=mv.get("hash", ""),
            mobile_version_vector=mv.get("version_vector", {}),
        )

        if result["status"] == "conflict":
            conflicts.append(result)
        elif result["status"] == "in_sync":
            synced += 1

    return {
        "status": "ok",
        "work_id": work_id,
        "device_id": device_id,
        "total_compared": len(mobile_versions),
        "in_sync": synced,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
    }


# --- WebSocket Handler ---

class SyncMessage(BaseModel):
    type: str
    work_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    request_id: Optional[str] = None


async def handle_sync_websocket(websocket: WebSocket, device_id: str):
    """WebSocket handler for real-time P2P sync."""
    engine = get_p2p_sync_engine()
    await websocket.accept()

    try:
        # Register device
        engine.register_device(device_id, {"name": device_id, "platform": "mobile"})

        # Send welcome
        await websocket.send_json({
            "type": "welcome",
            "device_id": device_id,
            "server_time": _now_iso(),
        })

        while True:
            raw = await websocket.receive_json()
            msg = SyncMessage(**raw)

            if msg.type == "ping":
                await websocket.send_json({"type": "pong", "request_id": msg.request_id})

            elif msg.type == "compare":
                work_id = msg.work_id or msg.payload.get("work_id")
                doc_type = msg.payload.get("doc_type")
                doc_id = msg.payload.get("doc_id")
                if work_id and doc_type and doc_id:
                    result = engine.compare_versions(
                        device_id=device_id,
                        work_id=work_id,
                        doc_type=doc_type,
                        doc_id=doc_id,
                        mobile_hash=msg.payload.get("mobile_hash", ""),
                        mobile_version_vector=msg.payload.get("mobile_version_vector", {}),
                    )
                    await websocket.send_json({
                        "type": "compare_result",
                        "request_id": msg.request_id,
                        "payload": result,
                    })

            elif msg.type == "resolve":
                work_id = msg.work_id or msg.payload.get("work_id")
                doc_type = msg.payload.get("doc_type")
                doc_id = msg.payload.get("doc_id")
                if work_id and doc_type and doc_id:
                    result = engine.resolve_conflict(
                        work_id=work_id,
                        doc_type=doc_type,
                        doc_id=doc_id,
                        mobile_payload=msg.payload.get("mobile_payload", {}),
                        mobile_hash=msg.payload.get("mobile_hash", ""),
                        mobile_version_vector=msg.payload.get("mobile_version_vector", {}),
                        strategy=msg.payload.get("strategy", "lww_mobile"),
                        device_id=device_id,
                    )
                    await websocket.send_json({
                        "type": "resolve_result",
                        "request_id": msg.request_id,
                        "payload": result,
                    })

            elif msg.type == "differential":
                work_id = msg.work_id or msg.payload.get("work_id")
                if work_id:
                    result = engine.compute_differential_payload(
                        device_id=device_id,
                        work_id=work_id,
                        since_version_vector=msg.payload.get("since_version_vector", {}),
                    )
                    await websocket.send_json({
                        "type": "differential_result",
                        "request_id": msg.request_id,
                        "payload": result,
                    })

            elif msg.type == "ack":
                work_id = msg.work_id or msg.payload.get("work_id")
                if work_id:
                    result = engine.ack_sync(
                        device_id=device_id,
                        work_id=work_id,
                        applied_changes=msg.payload.get("applied_changes", []),
                    )
                    await websocket.send_json({
                        "type": "ack_result",
                        "request_id": msg.request_id,
                        "payload": result,
                    })

            elif msg.type == "reconcile":
                work_id = msg.work_id or msg.payload.get("work_id")
                if work_id:
                    result = engine.resolve_conflict(
                        work_id=work_id,
                        doc_type=msg.payload.get("doc_type", ""),
                        doc_id=msg.payload.get("doc_id", ""),
                        mobile_payload=msg.payload.get("mobile_payload", {}),
                        mobile_hash=msg.payload.get("mobile_hash", ""),
                        mobile_version_vector=msg.payload.get("mobile_version_vector", {}),
                        strategy=msg.payload.get("strategy", "lww_mobile"),
                        device_id=device_id,
                    )
                    await websocket.send_json({
                        "type": "reconcile_result",
                        "request_id": msg.request_id,
                        "payload": result,
                    })

            elif msg.type == "status":
                result = engine.get_sync_status(device_id)
                await websocket.send_json({
                    "type": "status_result",
                    "request_id": msg.request_id,
                    "payload": result,
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({
            "type": "error",
            "error": str(exc),
            "request_id": msg.request_id if 'msg' in locals() else None,
        })
    finally:
        pass


@router.websocket("/ws/{device_id}")
async def sync_websocket(websocket: WebSocket, device_id: str):
    await handle_sync_websocket(websocket, device_id)


@router.websocket("/ws")
async def sync_websocket_generic(websocket: WebSocket):
    device_id = websocket.query_params.get("device_id", f"unknown_{uuid.uuid4().hex[:8]}")
    await handle_sync_websocket(websocket, device_id)