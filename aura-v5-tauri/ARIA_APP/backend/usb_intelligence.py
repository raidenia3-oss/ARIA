"""USB Intelligence — Detecta + Integra USB (UNIFIED).

Fusiona: original ARIA_APP/backend/usb_intelligence.py + ARIA_v4 version.
Best of both: registration, learning, caching, backups, clean structure.
"""

import os
import json
import string
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class USBIntelligence:
    """Detecta USB automáticamente + expande ARIA (unificado)."""

    def __init__(self):
        self.usb_devices = []
        self.aria_expansion = None
        self.learning_db = Path('ARIA_APP/usb_learning.json')
        self.learning_db.parent.mkdir(parents=True, exist_ok=True)

    async def detect_usb_devices(self) -> list:
        """Detecta TODOS los USB conectados (Windows/Linux/Mac)."""
        detected = []

        if os.name == 'nt':
            for drive in string.ascii_uppercase:
                path = f"{drive}:\\"
                try:
                    if os.path.exists(path):
                        if self._is_removable_drive(drive):
                            total, used, free = self._get_disk_space(path)
                            detected.append({
                                'path': path,
                                'drive': drive,
                                'type': 'USB',
                                'total_gb': total,
                                'used_gb': used,
                                'free_gb': free,
                                'timestamp': datetime.now().isoformat(),
                            })
                except Exception:
                    pass
        else:
            for mount_point in ['/media', '/mnt']:
                if os.path.exists(mount_point):
                    for device in os.listdir(mount_point):
                        path = os.path.join(mount_point, device)
                        if os.path.ismount(path):
                            total, used, free = self._get_disk_space(path)
                            detected.append({
                                'path': path,
                                'type': 'USB',
                                'total_gb': total,
                                'used_gb': used,
                                'free_gb': free,
                                'timestamp': datetime.now().isoformat(),
                            })

        self.usb_devices = detected
        return detected

    def _get_disk_space(self, path: str) -> tuple:
        try:
            stat = shutil.disk_usage(path)
            return (
                stat.total / (1024**3),
                stat.used / (1024**3),
                stat.free / (1024**3),
            )
        except Exception:
            return (0, 0, 0)

    def _is_removable_drive(self, drive_letter: str) -> bool:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            drive = f"{drive_letter}:\\"
            return kernel32.GetDriveTypeA(drive.encode()) == 2
        except Exception:
            return False

    async def get_usb_status(self) -> dict:
        await self.detect_usb_devices()
        status = {
            'usb_count': len(self.usb_devices),
            'devices': self.usb_devices,
            'total_expansion_gb': sum(d['total_gb'] for d in self.usb_devices),
            'available_gb': sum(d['free_gb'] for d in self.usb_devices),
            'detected': datetime.now().isoformat(),
        }
        return status

    async def expand_aria_with_usb(self) -> dict:
        if not self.usb_devices:
            await self.detect_usb_devices()

        expansion_items = {
            'models': [],
            'data': [],
            'cache': [],
            'backups': [],
        }

        for usb in self.usb_devices:
            usb_path = Path(usb['path'])

            for model_file in usb_path.rglob('*.gguf'):
                expansion_items['models'].append({
                    'path': str(model_file),
                    'size_mb': model_file.stat().st_size / (1024**2),
                    'type': 'GGUF model',
                })
            for model_file in usb_path.rglob('*.pt'):
                expansion_items['models'].append({
                    'path': str(model_file),
                    'size_mb': model_file.stat().st_size / (1024**2),
                    'type': 'PyTorch model',
                })
            for model_file in usb_path.rglob('*.bin'):
                expansion_items['models'].append({
                    'path': str(model_file),
                    'size_mb': model_file.stat().st_size / (1024**2),
                    'type': 'Binary model',
                })
            for data_file in usb_path.rglob('*.jsonl'):
                expansion_items['data'].append({
                    'path': str(data_file),
                    'size_mb': data_file.stat().st_size / (1024**2),
                    'type': 'Training data',
                })
            for cache_dir in usb_path.glob('aria_cache'):
                if cache_dir.exists():
                    expansion_items['cache'].append({
                        'path': str(cache_dir),
                        'type': 'Cache database',
                    })
            for backup_dir in usb_path.glob('aria_backup_*'):
                if backup_dir.exists():
                    expansion_items['backups'].append({
                        'path': str(backup_dir),
                        'timestamp': backup_dir.name.replace('aria_backup_', ''),
                        'type': 'System backup',
                    })

        self.aria_expansion = expansion_items
        return expansion_items

    async def register_usb_learning(self):
        """Registra datos del USB para que ARIA aprenda de ellos."""
        learning_data = {
            'usb_detected': datetime.now().isoformat(),
            'devices': self.usb_devices,
            'expansion': self.aria_expansion,
            'learning_items': [],
        }

        if self.aria_expansion and self.aria_expansion.get('data'):
            for data_item in self.aria_expansion['data']:
                learning_data['learning_items'].append({
                    'source': data_item['path'],
                    'type': 'Training data',
                    'ready_for_learning': True,
                })

        if self.aria_expansion and self.aria_expansion.get('models'):
            for model_item in self.aria_expansion['models']:
                learning_data['learning_items'].append({
                    'source': model_item['path'],
                    'type': 'Model',
                    'ready_for_loading': True,
                })

        try:
            with open(self.learning_db, 'w') as f:
                json.dump(learning_data, f, indent=2)
        except Exception as e:
            print(f"[USB] Learning save error: {e}")

        return learning_data

    async def get_usb_status_api(self):
        """GET /api/aria/usb/status — endpoint para app.py."""
        status = await self.get_usb_status()
        return status

    async def get_usb_expansion_api(self):
        """GET /api/aria/usb/expand — endpoint para app.py."""
        expansion = await self.expand_aria_with_usb()
        await self.register_usb_learning()
        return expansion


async def handle_usb_status():
    """Endpoint: GET /api/aria/usb/status."""
    usb = USBIntelligence()
    return await usb.get_usb_status()


async def handle_usb_expansion():
    """Endpoint: GET /api/aria/usb/expand."""
    usb = USBIntelligence()
    expansion = await usb.expand_aria_with_usb()
    await usb.register_usb_learning()
    return expansion
