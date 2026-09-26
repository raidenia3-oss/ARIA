"""BLOQUE 85 - Encrypted Snapshot Manager + Disaster Recovery (parte 1/3)."""
from __future__ import annotations
import hashlib
import json
import os
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from cryptography.fernet import Fernet
STORE_SUBDIR = "backend/recovery_state/snapshots"
KEY_FILENAME = ".recovery.key"
VALID_KINDS = ("full", "incremental")

def _store_dir() -> Path:
    d = Path(os.getenv("AURA_RECOVERY_DIR", STORE_SUBDIR))
    if not d.is_absolute():
        d = Path.cwd() / d
    d.mkdir(parents=True, exist_ok=True)
    return d

def _load_or_create_key(store: Path) -> bytes:
    kf = store / KEY_FILENAME
    if kf.exists():
        return kf.read_bytes().strip()
    key = Fernet.generate_key()
    kf.write_bytes(key)
    try:
        os.chmod(kf, 0o600)
    except Exception:
        pass
    return key

@dataclass
class SnapshotMetadata:
    snapshot_id: str = ""
    kind: str = "full"
    label: str = ""
    created_at: float = 0.0
    archive_path: str = ""
    size_bytes: int = 0
    sha256: str = ""
    files: int = 0
    verified: bool = False
    def __post_init__(self) -> None:
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex[:12]
        if self.kind not in VALID_KINDS:
            raise ValueError(f"kind no soportado: {self.kind}")
        if not self.created_at:
            self.created_at = time.time()
    def to_dict(self) -> Dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "kind": self.kind, "label": self.label,
                "created_at": self.created_at, "archive_path": Path(self.archive_path).name,
                "size_bytes": self.size_bytes, "sha256": self.sha256, "files": self.files,
                "verified": self.verified, "offline_only": True}

class RecoveryEngine:
    def __init__(self, store_dir: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._store = Path(store_dir) if store_dir else _store_dir()
        self._store.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(_load_or_create_key(self._store))
        self._snaps: Dict[str, SnapshotMetadata] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._recoveries: List[Dict[str, Any]] = []
        self._scan()
    def _scan(self) -> None:
        for meta_p in sorted(self._store.glob("*.meta.json")):
            try:
                d = json.loads(meta_p.read_text(encoding="utf-8"))
                m = SnapshotMetadata(snapshot_id=d["snapshot_id"], kind=d.get("kind", "full"),
                    label=d.get("label", ""), created_at=d.get("created_at", 0.0),
                    archive_path=str(self._store / d.get("archive", "")),
                    size_bytes=d.get("size_bytes", 0), sha256=d.get("sha256", ""),
                    files=d.get("files", 0), verified=d.get("verified", False))
                if Path(m.archive_path).exists():
                    self._snaps[m.snapshot_id] = m
            except Exception:
                continue
    def on_recovery(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)
    def _notify(self, evt: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._watchers)
        for cb in cbs:
            try:
                cb(evt)
            except Exception:
                pass
    def create_snapshot(self, sources: Dict[str, str], kind: str = "full", label: str = "") -> SnapshotMetadata:
        meta = SnapshotMetadata(kind=kind, label=label)
        tmp_plain = self._store / f".{meta.snapshot_id}.plain.zip"
        tmp_enc = self._store / f"{meta.snapshot_id}.snap.enc"
        count = 0
        with zipfile.ZipFile(tmp_plain, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for arcname, real in sources.items():
                p = Path(real)
                if p.is_file():
                    zf.write(p, arcname)
                    count += 1
                elif p.is_dir():
                    for f in sorted(p.rglob("*")):
                        if f.is_file() and KEY_FILENAME not in f.parts and f.suffix != ".enc":
                            zf.write(f, f"{arcname}/{f.relative_to(p).as_posix()}")
                            count += 1
        raw = tmp_plain.read_bytes()
        tmp_plain.unlink(missing_ok=True)
        enc = self._fernet.encrypt(raw)
        tmp_enc.write_bytes(enc)
        digest = hashlib.sha256(enc).hexdigest()
        meta.archive_path = str(tmp_enc)
        meta.size_bytes = len(enc)
        meta.sha256 = digest
        meta.files = count
        meta.verified = True
        sidecar = self._store / f"{meta.snapshot_id}.meta.json"
        sidecar.write_text(json.dumps({"snapshot_id": meta.snapshot_id, "kind": meta.kind,
            "label": meta.label, "created_at": meta.created_at, "archive": tmp_enc.name,
            "size_bytes": meta.size_bytes, "sha256": meta.sha256, "files": meta.files,
            "verified": True}, indent=2), encoding="utf-8")
        with self._lock:
            self._snaps[meta.snapshot_id] = meta
        return meta
    def rollback_last_stable(self, dest_dir: str, overwrite: bool = False) -> Dict[str, Any]:
        """Automated Disaster Recovery & Rollback Controller (100% local).

        Selecciona la instantanea verificada mas reciente (ultimo estado
        estable) y la restaura en dest_dir. Re-verifica integridad antes
        de restaurar; si ninguna es valida, reporta sin tocar el destino.
        """
        candidates = sorted(self.list_snapshots(), key=lambda m: m.created_at, reverse=True)
        for meta in candidates:
            v = self.verify(meta.snapshot_id)
            if v.get("verified"):
                out = self.restore(meta.snapshot_id, dest_dir, overwrite)
                if out.get("restored"):
                    return {"rolled_back": True, "snapshot_id": meta.snapshot_id, **out}
        return {"rolled_back": False, "reason": "no verified snapshot available",
                "offline_only": True}

    def list_snapshots(self) -> List[SnapshotMetadata]:
        with self._lock:
            return sorted(self._snaps.values(), key=lambda m: m.created_at)
    def get(self, snapshot_id: str) -> Optional[SnapshotMetadata]:
        with self._lock:
            return self._snaps.get(snapshot_id)
    def verify(self, snapshot_id: str) -> Dict[str, Any]:
        meta = self.get(snapshot_id)
        if meta is None:
            return {"verified": False, "reason": "not found"}
        p = Path(meta.archive_path)
        if not p.exists():
            return {"verified": False, "reason": "archive missing"}
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        ok = digest == meta.sha256
        meta.verified = ok
        return {"snapshot_id": snapshot_id, "verified": ok, "sha256": digest,
                "expected": meta.sha256, "offline_only": True}
    def delete(self, snapshot_id: str) -> bool:
        with self._lock:
            meta = self._snaps.pop(snapshot_id, None)
        if meta is None:
            return False
        Path(meta.archive_path).unlink(missing_ok=True)
        (self._store / f"{snapshot_id}.meta.json").unlink(missing_ok=True)
        return True
    def restore(self, snapshot_id: str, dest_dir: str, overwrite: bool = False) -> Dict[str, Any]:
        meta = self.get(snapshot_id)
        if meta is None:
            return {"restored": False, "reason": "not found"}
        v = self.verify(snapshot_id)
        if not v["verified"]:
            return {"restored": False, "reason": "integrity check failed"}
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        raw = self._fernet.decrypt(Path(meta.archive_path).read_bytes())
        tmp_plain = self._store / f".{snapshot_id}.restore.zip"
        tmp_plain.write_bytes(raw)
        restored: List[str] = []
        with zipfile.ZipFile(tmp_plain, "r") as zf:
            for info in zf.infolist():
                target = (dest / info.filename).resolve()
                if dest.resolve() not in target.parents and target != dest.resolve():
                    continue
                if target.exists() and not overwrite:
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    restored.append(info.filename)
        tmp_plain.unlink(missing_ok=True)
        evt = {"snapshot_id": snapshot_id, "dest": str(dest), "files": len(restored),
               "ts": time.time(), "offline_only": True}
        with self._lock:
            self._recoveries.append(evt)
        self._notify({"type": "restored", **evt})
        return {"restored": True, **evt}
    def recoveries(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._recoveries[-limit:])

_global_rec: Optional[RecoveryEngine] = None
_rec_lock = threading.Lock()

def get_recovery_engine() -> RecoveryEngine:
    global _global_rec
    with _rec_lock:
        if _global_rec is None:
            _global_rec = RecoveryEngine()
        return _global_rec

def reset_recovery_engine() -> None:
    global _global_rec
    with _rec_lock:
        _global_rec = None
