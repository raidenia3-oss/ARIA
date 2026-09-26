# -*- coding: utf-8 -*-
"""AURA OS — USB Storage Manager.

Detects USB drives, mounts/unmounts, and offloads large files
to external storage automatically.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.USBStorage")


@dataclass
class USBDevice:
    device_id: str
    name: str
    mount_point: str
    total_gb: float
    free_gb: float
    used_gb: float
    filesystem: str
    connected_at: float = field(default_factory=time.time)


@dataclass
class OffloadJob:
    job_id: str
    source: str
    destination: str
    size_bytes: int
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    error: Optional[str] = None


class USBStorageManager:
    """Manages USB storage devices and file offloading."""

    LOG_FILE = Path("data/learning/usb_log.json")

    def __init__(self, config: Any = None) -> None:
        self.config = config or Path("data")
        self.usb_devices: Dict[str, USBDevice] = {}
        self.offload_queue: List[OffloadJob] = []
        self.offload_history: List[OffloadJob] = []
        self._scan_cache: Dict[str, Any] = {}
        self._scan_cache_time = 0.0
        self._log_file = self.config / "learning" / "usb_log.json" if isinstance(self.config, Path) else Path("data/learning/usb_log.json")
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

    def scan_usb(self, force: bool = False) -> List[USBDevice]:
        now = time.time()
        if not force and now - self._scan_cache_time < 60:
            return list(self._scan_cache.get("devices", []))

        devices: List[USBDevice] = []
        mounts = self._detect_mounts()

        for mount in mounts:
            try:
                usage = self._get_usage(mount)
                if usage:
                    device_id = f"usb-{mount.lower().replace(':', '').replace('/', '-')}"
                    device = USBDevice(
                        device_id=device_id,
                        name=os.path.basename(mount) or "USB",
                        mount_point=mount,
                        total_gb=usage["total"],
                        free_gb=usage["free"],
                        used_gb=usage["used"],
                        filesystem=usage.get("fs", "unknown"),
                    )
                    devices.append(device)
                    self.usb_devices[device_id] = device
            except Exception as exc:
                logger.debug("USB scan error at %s: %s", mount, exc)

        self._scan_cache = {"devices": devices, "timestamp": now}
        self._scan_cache_time = now
        logger.info("USB scan: %d devices found", len(devices))
        return devices

    def _detect_mounts(self) -> List[str]:
        mounts: List[str] = []
        if os.name == "nt":
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                path = f"{letter}:\\"
                if os.path.exists(path):
                    drives = os.listdir(path) if os.path.isdir(path) else []
                    if any(d.lower() not in {"$recycle.bin", "system volume information"} for d in drives):
                        mounts.append(path)
        else:
            try:
                result = os.popen("mount | grep -E '/mnt/' 2>/dev/null || df -h | grep /dev/sd").read()
                for line in result.strip().split("\n"):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 6:
                            mounts.append(parts[5])
            except Exception:
                pass
            for p in ["/mnt/usb", "/mnt/external", "/media/*"]:
                import glob
                for m in glob.glob(p):
                    if m not in mounts:
                        mounts.append(m)
        return mounts

    def _get_usage(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            stat = shutil.disk_usage(path)
            total = stat.total / (1024 ** 3)
            free = stat.free / (1024 ** 3)
            used = stat.used / (1024 ** 3)
            return {"total": round(total, 2), "free": round(free, 2), "used": round(used, 2)}
        except Exception:
            return None

    def find_usb(self, min_free_gb: float = 1.0) -> Optional[USBDevice]:
        self.scan_usb()
        candidates = [
            d for d in self.usb_devices.values()
            if d.free_gb >= min_free_gb and d.used_gb < d.total_gb * 0.9
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda d: d.free_gb, reverse=True)
        return candidates[0]

    def is_usb_available(self, min_free_gb: float = 1.0) -> Tuple[bool, Optional[USBDevice]]:
        device = self.find_usb(min_free_gb)
        return (device is not None, device)

    def offload_file(self, source_path: str, device_id: str = None) -> OffloadJob:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        size_bytes = source.stat().st_size
        if device_id:
            device = self.usb_devices.get(device_id)
        else:
            device = self.find_usb(min_free_gb=size_bytes / (1024 ** 3))

        if not device:
            raise RuntimeError(f"No USB device with {size_bytes / (1024**3):.1f}GB free")

        job_id = f"OFF-{int(time.time())}-{len(self.offload_queue)}"
        dest = Path(device.mount_point) / source.name
        job = OffloadJob(
            job_id=job_id,
            source=str(source),
            destination=str(dest),
            size_bytes=size_bytes,
        )
        self.offload_queue.append(job)
        self._execute_offload(job)
        return job

    def _execute_offload(self, job: OffloadJob) -> None:
        job.status = "running"
        job.started_at = time.time()
        try:
            source = Path(job.source)
            dest = Path(job.destination)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            job.status = "completed"
            job.completed_at = time.time()
            logger.info("Offloaded %s -> %s (%.2f MB)", job.source, job.destination, job.size_bytes / (1024**2))
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            logger.error("Offload failed: %s", exc)
        self.offload_history.append(job)
        self._save_log()

    def auto_offload(self, directory: str = "data", min_size_mb: int = 500) -> List[OffloadJob]:
        dir_path = Path(directory)
        if not dir_path.exists():
            return []
        completed = []
        for f in sorted(dir_path.rglob("*"), key=lambda x: x.stat().st_size if x.is_file() else 0, reverse=True):
            if f.is_file() and f.stat().st_size >= min_size_mb * 1024 * 1024:
                try:
                    job = self.offload_file(str(f))
                    if job.status == "completed":
                        completed.append(job)
                except Exception as exc:
                    logger.debug("Auto-offload skip %s: %s", f, exc)
        return completed

    def get_usb_status(self) -> Dict[str, Any]:
        self.scan_usb()
        return {
            "connected": list(self.usb_devices.values()),
            "total_devices": len(self.usb_devices),
            "offload_queue": len(self.offload_queue),
            "offload_history": len(self.offload_history),
            "total_offloaded_bytes": sum(j.size_bytes for j in self.offload_history if j.status == "completed"),
        }

    def get_offload_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [j.__dict__ for j in self.offload_history[-limit:]]

    def _save_log(self) -> None:
        try:
            data = [j.__dict__ for j in self.offload_history]
            self._log_file.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.debug("USB log save failed: %s", exc)

    def _load_history(self) -> None:
        try:
            if self._log_file.exists():
                data = json.loads(self._log_file.read_text())
                for entry in data[-50:]:
                    job = OffloadJob(
                        job_id=entry.get("job_id", ""),
                        source=entry.get("source", ""),
                        destination=entry.get("destination", ""),
                        size_bytes=entry.get("size_bytes", 0),
                        status=entry.get("status", "unknown"),
                        started_at=entry.get("started_at", 0.0),
                        completed_at=entry.get("completed_at", 0.0),
                        error=entry.get("error"),
                    )
                    self.offload_history.append(job)
        except Exception:
            pass


usb_storage_manager = USBStorageManager()
