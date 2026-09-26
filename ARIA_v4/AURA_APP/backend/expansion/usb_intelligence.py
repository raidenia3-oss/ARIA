"""USB Intelligence — Detecta + Integra USB"""

import os
import string
from pathlib import Path
from datetime import datetime


class USBIntelligence:
    """Detecta USB automáticamente + expande ARIA"""

    def __init__(self):
        self.usb_devices = []

    async def detect_usb_devices(self) -> list:
        """Detecta USBs conectados (Windows/Linux)"""
        detected = []

        if os.name == 'nt':
            for drive in string.ascii_uppercase:
                path = f"{drive}:\\"
                try:
                    if os.path.exists(path):
                        if self._is_removable(drive):
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
                except:
                    pass
        else:
            for mount in ['/media', '/mnt']:
                if os.path.exists(mount):
                    for device in os.listdir(mount):
                        path = os.path.join(mount, device)
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
            import shutil
            stat = shutil.disk_usage(path)
            return (
                stat.total / (1024**3),
                stat.used / (1024**3),
                stat.free / (1024**3),
            )
        except:
            return (0, 0, 0)

    def _is_removable(self, drive_letter: str) -> bool:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            return kernel32.GetDriveTypeA(f"{drive_letter}:\\".encode()) == 2
        except:
            return False

    async def get_usb_status(self) -> dict:
        await self.detect_usb_devices()
        return {
            'usb_count': len(self.usb_devices),
            'devices': self.usb_devices,
            'total_expansion_gb': sum(d['total_gb'] for d in self.usb_devices),
            'available_gb': sum(d['free_gb'] for d in self.usb_devices),
            'detected': datetime.now().isoformat(),
        }

    async def expand_aria_with_usb(self) -> dict:
        if not self.usb_devices:
            await self.detect_usb_devices()

        expansion = {'models': [], 'data': [], 'skills': []}

        for usb in self.usb_devices:
            usb_path = Path(usb['path'])

            for model_file in usb_path.rglob('*.gguf'):
                expansion['models'].append({
                    'path': str(model_file),
                    'size_mb': model_file.stat().st_size / (1024**2),
                })
            for data_file in usb_path.rglob('*.jsonl'):
                expansion['data'].append({
                    'path': str(data_file),
                    'size_mb': data_file.stat().st_size / (1024**2),
                })
            for skill_file in usb_path.rglob('*.json'):
                if 'skill' in skill_file.name:
                    expansion['skills'].append({
                        'path': str(skill_file),
                        'name': skill_file.stem,
                    })

        return expansion


if __name__ == '__main__':
    import asyncio
    usb = USBIntelligence()
    status = asyncio.run(usb.get_usb_status())
    print(f"USBs detected: {status['usb_count']}")
    if status['usb_count'] > 0:
        expansion = asyncio.run(usb.expand_aria_with_usb())
        print(f"Models: {len(expansion['models'])}")
        print(f"Data: {len(expansion['data'])}")
