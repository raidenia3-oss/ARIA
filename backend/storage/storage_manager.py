# -*- coding: utf-8 -*-
"""AURA OS — Storage Manager.

Auto-offloads files, compresses videos, cleans cache,
and manages storage lifecycle.
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
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Storage")


@dataclass
class StorageReport:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    by_extension: Dict[str, int]
    largest_files: List[Dict[str, Any]]
    cache_files: List[str]
    last_scan: float = field(default_factory=time.time)


class StorageManager:
    """Manages storage: auto-offload, compress, cleanup."""

    COMPRESS_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv"}
    CACHE_EXTENSIONS = {".tmp", ".cache", ".log", ".bak", ".swp"}
    MAX_CACHE_SIZE_MB = 500

    def __init__(self, storage_dir: str = "storage", config: Any = None) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self._reports: List[StorageReport] = []
        self._compressed: List[str] = []
        self._cleaned: List[str] = []

    def scan_storage(self, directories: List[str] = None) -> StorageReport:
        dirs = directories or [str(self.storage_dir), "data"]
        total = 0
        by_ext: Dict[str, int] = {}
        files_info: List[Dict[str, Any]] = []
        cache_files: List[str] = []

        for dir_path in dirs:
            p = Path(dir_path)
            if not p.exists():
                continue
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    size = f.stat().st_size
                    total += size
                    ext = f.suffix.lower()
                    by_ext[ext] = by_ext.get(ext, 0) + size
                    files_info.append({
                        "path": str(f),
                        "size": size,
                        "extension": ext,
                        "modified": f.stat().st_mtime,
                    })
                    if ext in self.CACHE_EXTENSIONS:
                        cache_files.append(str(f))
                except (PermissionError, OSError):
                    continue

        files_info.sort(key=lambda x: x["size"], reverse=True)
        largest = files_info[:20]

        report = StorageReport(
            total_bytes=total,
            used_bytes=total,
            free_bytes=0,
            by_extension=by_ext,
            largest_files=largest,
            cache_files=cache_files,
        )
        self._reports.append(report)
        logger.info("Storage scan: %d bytes, %d files", total, len(files_info))
        return report

    def cleanup_cache(self, max_size_mb: int = None) -> Dict[str, Any]:
        max_size = max_size_mb or self.MAX_CACHE_SIZE_MB
        max_bytes = max_size * 1024 * 1024
        total_cleaned = 0
        cleaned_files: List[str] = []

        for report in reversed(self._reports):
            for fpath in report.cache_files:
                p = Path(fpath)
                if p.exists():
                    try:
                        size = p.stat().st_size
                        if total_cleaned + size <= max_bytes or not cleaned_files:
                            p.unlink()
                            total_cleaned += size
                            cleaned_files.append(fpath)
                            self._cleaned.append(fpath)
                    except (PermissionError, OSError):
                        continue

        return {
            "cleaned_files": cleaned_files,
            "total_cleaned_bytes": total_cleaned,
            "total_cleaned_mb": round(total_cleaned / (1024**2), 2),
            "files_remaining": len(report.cache_files) - len(cleaned_files) if self._reports else 0,
        }

    def compress_videos(self, directory: str = "data") -> Dict[str, Any]:
        dir_path = Path(directory)
        if not dir_path.exists():
            return {"compressed": [], "total_saved_bytes": 0}

        compressed = []
        total_saved = 0

        for f in dir_path.rglob("*"):
            if f.is_file() and f.suffix.lower() in self.COMPRESS_EXTENSIONS:
                original_size = f.stat().st_size
                compressed_path = f.with_suffix(f.suffix + ".gz")
                try:
                    with open(f, "rb") as src, open(compressed_path, "wb") as dst:
                        import gzip
                        with gzip.GzipFile(fileobj=dst, mode="wb") as gz:
                            gz.write(src.read())
                    compressed_size = compressed_path.stat().st_size
                    savings = original_size - compressed_size
                    if savings > 0:
                        total_saved += savings
                        compressed.append({
                            "original": str(f),
                            "compressed": str(compressed_path),
                            "original_size": original_size,
                            "compressed_size": compressed_size,
                            "savings_pct": round(savings / original_size * 100, 1),
                        })
                        self._compressed.append(str(compressed_path))
                        f.unlink()
                except Exception as exc:
                    logger.debug("Compress %s: %s", f, exc)

        return {
            "compressed": compressed,
            "total_saved_bytes": total_saved,
            "total_saved_mb": round(total_saved / (1024**2), 2),
            "files_compressed": len(compressed),
        }

    def get_storage_summary(self) -> Dict[str, Any]:
        latest = self._reports[-1] if self._reports else self.scan_storage()
        return {
            "total_bytes": latest.total_bytes,
            "total_mb": round(latest.total_bytes / (1024**2), 2),
            "by_extension": latest.by_extension,
            "largest_files": latest.largest_files[:5],
            "cache_files_count": len(latest.cache_files),
            "reports_count": len(self._reports),
            "compressed_files": len(self._compressed),
            "cleaned_files": len(self._cleaned),
        }

    def auto_cleanup(self) -> Dict[str, Any]:
        cache_result = self.cleanup_cache()
        compress_result = self.compress_videos()
        return {
            "cache_cleanup": cache_result,
            "video_compression": compress_result,
            "total_cleanup_mb": cache_result["total_cleaned_mb"] + compress_result["total_saved_mb"],
        }


storage_manager = StorageManager()
