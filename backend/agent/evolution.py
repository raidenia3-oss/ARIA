"""AURA Local Self-Evolution, Auto-Patching & Offline Model Fine-Tuning Engine (Bloque 60).

Motor 100% offline para:
1. Auto-parcheo: snapshot -> parche -> validacion sintaxis -> pruebas sandbox -> rollback si falla.
2. Construccion de datasets para fine-tuning local LoRA (advisory, sin entrenamiento real).
3. Orquestador de fine-tuning local: programacion, checkpoints, metricas, sin dependencias cloud.

Almacenamiento: data/evolution/{patches,datasets,backups,checkpoints,logs}/
No introduce dependencias externas. Usa hashlib, json, pathlib, subprocess (sandbox).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.Agent.Evolution")

DATA_DIR = Path(os.getenv("AURA_EVOLUTION_DIR", os.path.join(os.getcwd(), "data", "evolution")))
for _sub in ("patches", "datasets", "backups", "checkpoints", "logs"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _safe_rel(path: str) -> str:
    return str(path).replace(os.sep, "/").lstrip("/")

class PatchStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass
class PatchRecord:
    patch_id: str
    target_file: str
    original_hash: str
    patched_hash: str
    diff: str
    status: PatchStatus
    created_at: str
    applied_at: Optional[str] = None
    rolled_back_at: Optional[str] = None
    sandbox_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "target_file": self.target_file,
            "original_hash": self.original_hash,
            "patched_hash": self.patched_hash,
            "diff": self.diff,
            "status": self.status.value,
            "created_at": self.created_at,
            "applied_at": self.applied_at,
            "rolled_back_at": self.rolled_back_at,
            "sandbox_result": self.sandbox_result,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class DatasetEntry:
    entry_id: str
    instruction: str
    input: str
    output: str
    source: str
    quality_score: float
    created_at: str = field(default_factory=lambda: _now_iso())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
            "source": self.source,
            "quality_score": self.quality_score,
            "created_at": self.created_at,
        }


@dataclass
class FineTuneJob:
    job_id: str
    dataset_id: str
    base_model: str
    status: str
    created_at: str
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkpoint_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    advisory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "base_model": self.base_model,
            "status": self.status,
            "created_at": self.created_at,
            "scheduled_at": self.scheduled_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "checkpoint_ids": self.checkpoint_ids,
            "metrics": self.metrics,
            "error": self.error,
            "advisory": self.advisory,
        }

class EvolutionEngine:
    """Motor de auto-evolucion, auto-parcheo y fine-tuning local (100% offline)."""

    MAX_PATCH_SIZE = 20000
    MIN_PATCH_LINES = 1

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        for _sub in ("patches", "datasets", "backups", "checkpoints", "logs"):
            (self.data_dir / _sub).mkdir(parents=True, exist_ok=True)
        self._patches_dir = self.data_dir / "patches"
        self._datasets_dir = self.data_dir / "datasets"
        self._backups_dir = self.data_dir / "backups"
        self._checkpoints_dir = self.data_dir / "checkpoints"
        self._logs_dir = self.data_dir / "logs"
        self._lock = threading.RLock()
        self._sandbox_runner = None

    @property
    def sandbox_runner(self):
        if self._sandbox_runner is None:
            try:
                from backend.agent.sandbox import get_sandbox_runner
                self._sandbox_runner = get_sandbox_runner()
            except Exception:
                self._sandbox_runner = None
        return self._sandbox_runner

    # ------------------------------------------------------------------ #
    # Snapshots / backups
    # ------------------------------------------------------------------ #
    def _backup_path(self, target: str) -> Path:
        safe = _safe_rel(target).replace("/", "_")
        return self._backups_dir / f"{safe}.bak"

    def snapshot_file(self, target: str) -> Dict[str, Any]:
        src = Path(target)
        if not src.is_file():
            raise FileNotFoundError(f"Archivo no encontrado: {target}")
        backup = self._backup_path(target)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, backup)
        meta = {
            "target": target,
            "backup": str(backup),
            "original_hash": _sha256_file(src),
            "size_bytes": src.stat().st_size,
            "timestamp": _now_iso(),
        }
        meta_path = backup.with_suffix(".json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        return meta

    def restore_backup(self, target: str) -> Dict[str, Any]:
        backup = self._backup_path(target)
        if not backup.is_file():
            raise FileNotFoundError(f"No existe backup para: {target}")
        meta_path = backup.with_suffix(".json")
        meta = {}
        if meta_path.is_file():
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta = json.load(fh)
        dst = Path(target)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, dst)
        return {
            "target": target,
            "restored_from": str(backup),
            "restored_hash": _sha256_file(dst),
            "timestamp": _now_iso(),
            "previous_meta": meta,
        }

    # ------------------------------------------------------------------ #
    # Patch generation
    # ------------------------------------------------------------------ #
    def _patch_path(self, patch_id: str) -> Path:
        return self._patches_dir / f"{patch_id}.patch.json"

    def generate_patch(
        self,
        target_file: str,
        old_snippet: str,
        new_snippet: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PatchRecord:
        with self._lock:
            src = Path(target_file)
            if not src.is_file():
                raise FileNotFoundError(f"Archivo no encontrado: {target_file}")
            content = src.read_text(encoding="utf-8")
            if old_snippet not in content:
                raise ValueError("El snippet original no se encuentra en el archivo")
            occurrences = content.count(old_snippet)
            if occurrences > 1:
                raise ValueError(
                    f"El snippet es ambiguo ({occurrences} coincidencias). "
                    "Proporciona contexto suficiente para que sea unico."
                )
            new_content = content.replace(old_snippet, new_snippet, 1)
            if len(new_content) > self.MAX_PATCH_SIZE:
                raise ValueError("El parche supera el tamano maximo permitido")
            diff = self._make_diff(content, new_content)
            original_hash = _sha256_file(src)
            patched_hash = _sha256_bytes(new_content.encode("utf-8"))
            patch_id = uuid.uuid4().hex[:16]
            record = PatchRecord(
                patch_id=patch_id,
                target_file=target_file,
                original_hash=original_hash,
                patched_hash=patched_hash,
                diff=diff,
                status=PatchStatus.PENDING,
                created_at=_now_iso(),
                metadata={
                    "description": description,
                    "occurrences": occurrences,
                    **(metadata or {}),
                },
            )
            with open(self._patch_path(patch_id), "w", encoding="utf-8") as fh:
                json.dump(record.to_dict(), fh, ensure_ascii=False, indent=2)
            self._log_event("patch_generated", {"patch_id": patch_id, "target": target_file})
            return record

    @staticmethod
    def _make_diff(old: str, new: str) -> str:
        import difflib
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="original",
            tofile="patched",
            lineterm="",
        )
        return "".join(diff)

    # ------------------------------------------------------------------ #
    # Patch application / validation / rollback
    # ------------------------------------------------------------------ #
    def apply_patch(self, patch_id: str, run_sandbox: bool = True) -> PatchRecord:
        with self._lock:
            path = self._patch_path(patch_id)
            if not path.is_file():
                raise FileNotFoundError(f"Parche no encontrado: {patch_id}")
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            record = PatchRecord(**{k: v for k, v in data.items() if k != "metadata"},
                                  metadata=data.get("metadata", {}))
            target = Path(record.target_file)
            if not target.is_file():
                record.status = PatchStatus.FAILED
                record.error = "Archivo objetivo no existe"
                self._save_record(record)
                return record
            current_hash = _sha256_file(target)
            if current_hash != record.original_hash:
                record.status = PatchStatus.REJECTED
                record.error = (
                    f"El archivo fue modificado fuera del motor "
                    f"(actual={current_hash[:12]}... original={record.original_hash[:12]}...)"
                )
                self._save_record(record)
                return record
            original_content = target.read_text(encoding="utf-8")
            new_content = self._apply_diff(original_content, record.diff)
            if not new_content:
                record.status = PatchStatus.FAILED
                record.error = "No se pudo aplicar el diff"
                self._save_record(record)
                return record
            sandbox_result = None
            if run_sandbox:
                sandbox_result = self._validate_in_sandbox(new_content, str(target))
                if sandbox_result.get("outcome") not in ("success", "passed"):
                    record.status = PatchStatus.FAILED
                    record.error = f"Sandbox rechazo el parche: {sandbox_result.get('stderr', '')[:200]}"
                    record.sandbox_result = sandbox_result
                    self._save_record(record)
                    return record
            target.write_text(new_content, encoding="utf-8")
            record.status = PatchStatus.APPLIED
            record.applied_at = _now_iso()
            record.sandbox_result = sandbox_result
            self._save_record(record)
            self._log_event("patch_applied", {"patch_id": patch_id, "target": record.target_file})
            return record

    def rollback_patch(self, patch_id: str) -> Dict[str, Any]:
        with self._lock:
            path = self._patch_path(patch_id)
            if not path.is_file():
                raise FileNotFoundError(f"Parche no encontrado: {patch_id}")
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            record = PatchRecord(**{k: v for k, v in data.items() if k != "metadata"},
                                  metadata=data.get("metadata", {}))
            if record.status != PatchStatus.APPLIED:
                raise ValueError(f"El parche no esta aplicado: {record.status.value}")
            restore = self.restore_backup(record.target_file)
            record.status = PatchStatus.ROLLED_BACK
            record.rolled_back_at = _now_iso()
            self._save_record(record)
            self._log_event("patch_rolled_back", {"patch_id": patch_id})
            return restore

    @staticmethod
    def _apply_diff(original: str, diff: str) -> Optional[str]:
        lines = original.splitlines(keepends=True)
        result: List[str] = []
        i = 0
        in_hunk = False
        hunk_lines: List[Tuple[str, str]] = []
        for raw in diff.splitlines():
            if raw.startswith("@@"):
                if in_hunk and hunk_lines:
                    result.extend(EvolutionEngine._apply_hunk(lines, i, hunk_lines))
                    hunk_lines = []
                in_hunk = True
                m = re.search(r"@@ -(\d+),?\d* \+(\d+),?\d* @@", raw)
                i = int(m.group(1)) - 1 if m else i
            elif raw.startswith(("+", "-", " ")):
                if in_hunk:
                    hunk_lines.append((raw[0], raw[1:]))
            elif raw.startswith("\\"):
                continue
        if in_hunk and hunk_lines:
            result.extend(EvolutionEngine._apply_hunk(lines, i, hunk_lines))
        if not result:
            return None
        return "".join(result)

    @staticmethod
    def _apply_hunk(lines: List[str], start: int, hunk: List[Tuple[str, str]]) -> List[str]:
        out: List[str] = []
        idx = start
        for op, text in hunk:
            if op == " ":
                if idx < len(lines) and lines[idx].rstrip("\n") == text.rstrip("\n"):
                    out.append(lines[idx])
                    idx += 1
                else:
                    return []
            elif op == "-":
                if idx < len(lines):
                    idx += 1
            elif op == "+":
                out.append(text + "\n" if not text.endswith("\n") else text)
        while idx < len(lines):
            out.append(lines[idx])
            idx += 1
        return out

    # ------------------------------------------------------------------ #
    # Syntax / sandbox validation
    # ------------------------------------------------------------------ #
    def _validate_in_sandbox(self, code: str, target: str) -> Dict[str, Any]:
        runner = self.sandbox_runner
        if runner is None:
            return {"outcome": "skipped", "reason": "sandbox_unavailable"}
        try:
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                runner.execute(
                    code=f"import ast; ast.parse(open({target!r}).read())",
                    language="python",
                    timeout=10.0,
                    memory_limit_mb=128.0,
                    cpu_limit_seconds=5.0,
                )
            )
            return result.to_dict()
        except Exception as exc:
            return {"outcome": "error", "error": str(exc)}

    def validate_syntax(self, code: str) -> Dict[str, Any]:
        try:
            compile(code, "<evolution>", "exec")
            return {"valid": True, "errors": []}
        except SyntaxError as exc:
            return {"valid": False, "errors": [f"{exc.__class__.__name__}: {exc}"]}

    def check_syntax_integrity(self, target: str) -> Dict[str, Any]:
        src = Path(target)
        if not src.is_file():
            return {"valid": False, "errors": ["Archivo no encontrado"]}
        code = src.read_text(encoding="utf-8")
        result = self.validate_syntax(code)
        result["file"] = target
        result["hash"] = _sha256_file(src)
        return result

    # ------------------------------------------------------------------ #
    # Dataset builder
    # ------------------------------------------------------------------ #
    def _dataset_path(self, dataset_id: str, split: DatasetSplit = DatasetSplit.TRAIN) -> Path:
        return self._datasets_dir / f"{dataset_id}_{split.value}.jsonl"

    def build_dataset(
        self,
        name: str,
        entries: List[Dict[str, Any]],
        description: str = "",
        splits: Optional[List[DatasetSplit]] = None,
        quality_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        with self._lock:
            splits = splits or [DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST]
            dataset_id = uuid.uuid4().hex[:12]
            validated: List[DatasetEntry] = []
            for raw in entries:
                instruction = str(raw.get("instruction", "")).strip()
                inp = str(raw.get("input", "")).strip()
                out = str(raw.get("output", "")).strip()
                source = str(raw.get("source", "unknown"))
                score = float(raw.get("quality_score", 1.0))
                if not instruction or not out:
                    continue
                if score < quality_threshold:
                    continue
                validated.append(DatasetEntry(
                    entry_id=uuid.uuid4().hex[:8],
                    instruction=instruction,
                    input=inp,
                    output=out,
                    source=source,
                    quality_score=score,
                ))
            rng = random.Random(dataset_id)
            rng.shuffle(validated)
            total = len(validated)
            if total == 0:
                raise ValueError("No hay entradas validas para construir el dataset")
            split_sizes = self._compute_splits(total, splits)
            written: Dict[str, int] = {}
            offset = 0
            for split in splits:
                size = split_sizes.get(split, 0)
                chunk = validated[offset:offset + size]
                path = self._dataset_path(dataset_id, split)
                with open(path, "w", encoding="utf-8") as fh:
                    for entry in chunk:
                        fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
                written[split.value] = len(chunk)
                offset += size
            manifest = {
                "dataset_id": dataset_id,
                "name": name,
                "description": description,
                "total_entries": total,
                "splits": written,
                "quality_threshold": quality_threshold,
                "created_at": _now_iso(),
            }
            with open(self._datasets_dir / f"{dataset_id}_manifest.json", "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, ensure_ascii=False, indent=2)
            self._log_event("dataset_built", {"dataset_id": dataset_id, "total": total})
            return manifest

    def list_datasets(self) -> List[Dict[str, Any]]:
        out = []
        for path in sorted(self._datasets_dir.glob("*_manifest.json")):
            with open(path, "r", encoding="utf-8") as fh:
                out.append(json.load(fh))
        return out

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        path = self._datasets_dir / f"{dataset_id}_manifest.json"
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def export_dataset(self, dataset_id: str, fmt: str = "jsonl") -> Dict[str, Any]:
        manifest = self.get_dataset(dataset_id)
        if not manifest:
            raise FileNotFoundError(f"Dataset no encontrado: {dataset_id}")
        out_dir = self._datasets_dir / f"{dataset_id}_export"
        out_dir.mkdir(parents=True, exist_ok=True)
        files = {}
        for split in (DatasetSplit.TRAIN, DatasetSplit.VALIDATION, DatasetSplit.TEST):
            src = self._dataset_path(dataset_id, split)
            if not src.is_file():
                continue
            dst = out_dir / f"{split.value}.jsonl"
            shutil.copy2(src, dst)
            files[split.value] = str(dst)
        return {"dataset_id": dataset_id, "format": fmt, "files": files, "out_dir": str(out_dir)}

    @staticmethod
    def _compute_splits(total: int, splits: List[DatasetSplit]) -> Dict[DatasetSplit, int]:
        if total < 3:
            return {DatasetSplit.TRAIN: total}
        if len(splits) == 1:
            return {splits[0]: total}
        if len(splits) == 3:
            train = int(total * 0.8)
            val = int(total * 0.1)
            test = total - train - val
            return {DatasetSplit.TRAIN: train, DatasetSplit.VALIDATION: val, DatasetSplit.TEST: test}
        half = total // 2
        return {splits[0]: half, splits[1]: total - half}

# ------------------------------------------------------------------ #
    def _save_record(self, record: PatchRecord) -> None:
        with open(self._patch_path(record.patch_id), "w", encoding="utf-8") as fh:
            json.dump(record.to_dict(), fh, ensure_ascii=False, indent=2)

    def list_patches(self, status: Optional[PatchStatus] = None) -> List[PatchRecord]:
        out: List[PatchRecord] = []
        for path in sorted(self._patches_dir.glob("*.patch.json")):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                rec = PatchRecord(**{k: v for k, v in data.items() if k != "metadata"},
                                   metadata=data.get("metadata", {}))
                if status is None or rec.status == status:
                    out.append(rec)
            except Exception as exc:
                logger.debug("Error cargando patch %s: %s", path, exc)
        return out

    def get_patch(self, patch_id: str) -> Optional[PatchRecord]:
        path = self._patch_path(patch_id)
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return PatchRecord(**{k: v for k, v in data.items() if k != "metadata"},
                            metadata=data.get("metadata", {}))

    def _log_event(self, event: str, payload: Dict[str, Any]) -> None:
        try:
            record = {"event": event, "timestamp": _now_iso(), "payload": payload}
            log_path = self._logs_dir / f"{event}_{uuid.uuid4().hex[:8]}.json"
            with open(log_path, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Error registrando evento %s: %s", event, exc)

    def list_logs(self, event: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for path in sorted(self._logs_dir.glob("*.json"), reverse=True):
            if event and not path.name.startswith(event):
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except Exception:
                continue
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    def get_status(self) -> Dict[str, Any]:
        patches = self.list_patches()
        datasets = self.list_datasets()
        jobs = self.lora_scheduler.list_jobs() if self.lora_scheduler else []
        return {
            "data_dir": str(self.data_dir),
            "patches": {
                "total": len(patches),
                "by_status": {s.value: sum(1 for p in patches if p.status == s) for s in PatchStatus},
            },
            "datasets": {"total": len(datasets), "total_entries": sum(d.get("total_entries", 0) for d in datasets)},
            "lora_jobs": {
                "total": len(jobs),
                "by_status": {j.status: sum(1 for k in jobs if k.status == j.status) for j in jobs},
            },
            "sandbox_available": self.sandbox_runner is not None,
            "offline": True,
        }

    @property
    def lora_scheduler(self) -> Optional[LoRAScheduler]:
        if not hasattr(self, "_lora_scheduler") or self._lora_scheduler is None:
            self._lora_scheduler = LoRAScheduler(self)
        return self._lora_scheduler


# ------------------------------------------------------------------ #
# Module-level singleton
# ------------------------------------------------------------------ #
class LoRAScheduler:
    """Programador de fine-tuning local LoRA.

    NO ejecuta entrenamiento real. Ofrece:
    - Planificacion de entrenamientos advisory.
    - Gestion de checkpoints metricos.
    - Estimacion de recursos locales.
    """

    def __init__(self, engine: "EvolutionEngine") -> None:
        self.engine = engine
        self._jobs: Dict[str, FineTuneJob] = {}
        self._load_jobs()

    def _jobs_path(self) -> Path:
        return self.engine._checkpoints_dir / "lora_jobs.json"

    def _load_jobs(self) -> None:
        path = self._jobs_path()
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            for raw in data:
                job = FineTuneJob(**raw)
                self._jobs[job.job_id] = job
        except Exception as exc:
            logger.debug("No se pudieron cargar jobs LoRA: %s", exc)

    def _save_jobs(self) -> None:
        with open(self._jobs_path(), "w", encoding="utf-8") as fh:
            json.dump([j.to_dict() for j in self._jobs.values()], fh, ensure_ascii=False, indent=2)

    def schedule_job(
        self,
        dataset_id: str,
        base_model: str = "local-base",
        priority: str = "normal",
        max_checkpoints: int = 3,
        estimated_minutes: int = 60,
    ) -> FineTuneJob:
        with self.engine._lock:
            manifest = self.engine.get_dataset(dataset_id)
            if not manifest:
                raise FileNotFoundError(f"Dataset no encontrado: {dataset_id}")
            job_id = uuid.uuid4().hex[:10]
            job = FineTuneJob(
                job_id=job_id,
                dataset_id=dataset_id,
                base_model=base_model,
                status="scheduled",
                created_at=_now_iso(),
                scheduled_at=_now_iso(),
                advisory=True,
                metrics={"priority": priority, "max_checkpoints": max_checkpoints,
                         "estimated_minutes": estimated_minutes},
            )
            self._jobs[job_id] = job
            self._save_jobs()
            self.engine._log_event("lora_job_scheduled", {"job_id": job_id, "dataset_id": dataset_id})
            return job

    def list_jobs(self) -> List[FineTuneJob]:
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[FineTuneJob]:
        return self._jobs.get(job_id)

    def start_job(self, job_id: str) -> FineTuneJob:
        with self.engine._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise FileNotFoundError(f"Job no encontrado: {job_id}")
            if job.status != "scheduled":
                raise ValueError(f"Job no esta programado: {job.status}")
            job.status = "running"
            job.started_at = _now_iso()
            self._save_jobs()
            self.engine._log_event("lora_job_started", {"job_id": job_id})
            return job

    def checkpoint_job(self, job_id: str, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self.engine._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise FileNotFoundError(f"Job no encontrado: {job_id}")
            if job.status != "running":
                raise ValueError(f"Job no esta en ejecucion: {job.status}")
            ck_id = uuid.uuid4().hex[:10]
            ck_path = self.engine._checkpoints_dir / f"{job_id}_{ck_id}.json"
            data = {
                "checkpoint_id": ck_id,
                "job_id": job_id,
                "dataset_id": job.dataset_id,
                "base_model": job.base_model,
                "created_at": _now_iso(),
                "metrics": metrics or {},
            }
            with open(ck_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            job.checkpoint_ids.append(ck_id)
            if metrics:
                job.metrics.update(metrics)
            self._save_jobs()
            self.engine._log_event("lora_checkpoint", {"job_id": job_id, "checkpoint_id": ck_id})
            return data

    def complete_job(self, job_id: str, metrics: Optional[Dict[str, Any]] = None) -> FineTuneJob:
        with self.engine._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise FileNotFoundError(f"Job no encontrado: {job_id}")
            job.status = "completed"
            job.completed_at = _now_iso()
            if metrics:
                job.metrics.update(metrics)
            self._save_jobs()
            self.engine._log_event("lora_job_completed", {"job_id": job_id})
            return job

    def fail_job(self, job_id: str, error: str) -> FineTuneJob:
        with self.engine._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise FileNotFoundError(f"Job no encontrado: {job_id}")
            job.status = "failed"
            job.error = error
            job.completed_at = _now_iso()
            self._save_jobs()
            self.engine._log_event("lora_job_failed", {"job_id": job_id, "error": error})
            return job

    def estimate_resources(self, dataset_id: str) -> Dict[str, Any]:
        manifest = self.engine.get_dataset(dataset_id)
        if not manifest:
            raise FileNotFoundError(f"Dataset no encontrado: {dataset_id}")
        total = manifest.get("total_entries", 0)
        return {
            "dataset_id": dataset_id,
            "total_entries": total,
            "estimated_vram_mb": max(2048, min(16384, total * 64)),
            "estimated_disk_mb": max(100, total * 2),
            "estimated_minutes": max(15, min(480, total // 10)),
            "advisory": True,
            "note": "Estimacion local; el entrenamiento real depende de hardware disponible",
        }


# Module-level singleton
# ------------------------------------------------------------------ #
_engine: Optional[EvolutionEngine] = None
_engine_lock = threading.Lock()


def get_evolution_engine() -> EvolutionEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = EvolutionEngine()
    return _engine


def reset_evolution_engine() -> None:
    global _engine
    with _engine_lock:
        _engine = None


__all__ = [
    "EvolutionEngine",
    "LoRAScheduler",
    "PatchRecord",
    "PatchStatus",
    "DatasetEntry",
    "DatasetSplit",
    "FineTuneJob",
    "get_evolution_engine",
    "reset_evolution_engine",
]
