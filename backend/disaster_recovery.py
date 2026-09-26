"""Disaster recovery for AURA backups, snapshots and restoration orchestration."""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class BackupStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"


@dataclass
class BackupMetadata:
    backup_id: str
    backup_type: BackupType
    status: BackupStatus = BackupStatus.PENDING
    size_bytes: int = 0
    checksum: Optional[str] = None
    encrypted: bool = False
    source: str = "unknown"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SnapshotManager:
    """Crea y verifica backups simulados."""

    def __init__(self, storage_dir: str = "/tmp/aura_backups") -> None:
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.backups: Dict[str, BackupMetadata] = {}

    def create_backup(self, backup_type: BackupType = BackupType.SNAPSHOT, source: str = "system") -> BackupMetadata:
        backup_id = f"backup-{int(time.time() * 1000)}"
        metadata = BackupMetadata(
            backup_id=backup_id,
            backup_type=backup_type,
            source=source,
        )
        self.backups[backup_id] = metadata
        return metadata

    def finalize_backup(self, backup_id: str, size_bytes: int = 0, checksum: Optional[str] = None, encrypted: bool = False) -> Optional[BackupMetadata]:
        backup = self.backups.get(backup_id)
        if not backup:
            return None
        backup.status = BackupStatus.COMPLETED
        backup.size_bytes = size_bytes
        backup.checksum = checksum or self._fake_checksum()
        backup.encrypted = encrypted
        backup.completed_at = datetime.utcnow().isoformat() + "Z"
        return backup

    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        backup = self.backups.get(backup_id)
        if not backup:
            return {"verified": False, "error": "backup not found"}
        if backup.status == BackupStatus.FAILED:
            return {"verified": False, "error": "backup failed"}
        backup.status = BackupStatus.VERIFIED
        return {"verified": True, "checksum": backup.checksum, "backup_id": backup_id}

    def list_backups(self) -> List[BackupMetadata]:
        return list(self.backups.values())

    def _fake_checksum(self) -> str:
        return hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]


class DisasterRecoveryManager:
    """Orquesta backup/restauración."""

    def __init__(self, snapshot_manager: Optional[SnapshotManager] = None) -> None:
        self.snapshot_manager = snapshot_manager or SnapshotManager()

    def create_snapshot(self, source: str = "system") -> Dict[str, Any]:
        backup = self.snapshot_manager.create_backup(BackupType.SNAPSHOT, source=source)
        return {"backup_id": backup.backup_id, "status": backup.status, "source": backup.source, "created_at": backup.created_at}

    def finalize_snapshot(self, backup_id: str, size_bytes: int = 0, encrypted: bool = False) -> Dict[str, Any]:
        backup = self.snapshot_manager.finalize_backup(backup_id, size_bytes=size_bytes, encrypted=encrypted)
        if not backup:
            return {"error": "backup not found"}
        return {"backup_id": backup.backup_id, "status": backup.status, "checksum": backup.checksum, "completed_at": backup.completed_at}

    def verify_snapshot(self, backup_id: str) -> Dict[str, Any]:
        return self.snapshot_manager.verify_backup(backup_id)

    def restore(self, backup_id: str, target: str = "current") -> Dict[str, Any]:
        backup = self.snapshot_manager.backups.get(backup_id)
        if not backup:
            return {"status": "failed", "error": "backup not found"}
        if backup.status not in (BackupStatus.COMPLETED, BackupStatus.VERIFIED):
            return {"status": "failed", "error": "backup not completed"}
        return {
            "status": "restored",
            "backup_id": backup_id,
            "target": target,
            "restored_at": datetime.utcnow().isoformat() + "Z",
            "checksum": backup.checksum,
        }

    def list_backups(self) -> Dict[str, Any]:
        backups = self.snapshot_manager.list_backups()
        return {
            "count": len(backups),
            "backups": [
                {
                    "backup_id": b.backup_id,
                    "type": b.backup_type.value,
                    "status": b.status.value,
                    "size_bytes": b.size_bytes,
                    "source": b.source,
                    "created_at": b.created_at,
                }
                for b in backups
            ],
        }
