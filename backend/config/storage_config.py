# -*- coding: utf-8 -*-
"""AURA OS — Storage Configuration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional


class StorageConfig:
    """Configuration for storage and offloading."""

    DEFAULT_DATA_DIR = Path("data")
    DEFAULT_STORAGE_DIR = Path("storage")
    USB_MOUNT_BASE = Path("/mnt") if os.name != "nt" else Path("D:")
    MAX_USB_SIZE_GB = 128
    MIN_FREE_SPACE_GB = 1.0
    AUTO_OFFLOAD_SIZE_MB = 500
    COMPRESS_THRESHOLD_MB = 100
    CACHE_MAX_AGE_DAYS = 7
    BACKUP_DIR = Path("backups")
    OFFLOAD_LOG = Path("data/learning/storage_log.json")

    def __init__(self, data_dir: str = None, storage_dir: str = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else self.DEFAULT_DATA_DIR
        self.storage_dir = Path(storage_dir) if storage_dir else self.DEFAULT_STORAGE_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    def get_offload_threshold_bytes(self) -> int:
        return self.AUTO_OFFLOAD_SIZE_MB * 1024 * 1024

    def get_compress_threshold_bytes(self) -> int:
        return self.COMPRESS_THRESHOLD_MB * 1024 * 1024

    def get_cache_max_age_seconds(self) -> int:
        return self.CACHE_MAX_AGE_DAYS * 86400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_dir": str(self.data_dir),
            "storage_dir": str(self.storage_dir),
            "usb_mount_base": str(self.USB_MOUNT_BASE),
            "max_usb_size_gb": self.MAX_USB_SIZE_GB,
            "min_free_space_gb": self.MIN_FREE_SPACE_GB,
            "auto_offload_size_mb": self.AUTO_OFFLOAD_SIZE_MB,
            "compress_threshold_mb": self.COMPRESS_THRESHOLD_MB,
            "cache_max_age_days": self.CACHE_MAX_AGE_DAYS,
            "backup_dir": str(self.BACKUP_DIR),
        }


storage_config = StorageConfig()
