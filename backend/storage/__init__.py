# -*- coding: utf-8 -*-
"""AURA OS — Storage Modules."""
from __future__ import annotations

from backend.storage.usb_storage_manager import USBStorageManager, usb_storage_manager
from backend.storage.storage_manager import StorageManager, storage_manager

__all__ = [
    "USBStorageManager", "usb_storage_manager",
    "StorageManager", "storage_manager",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
