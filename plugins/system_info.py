"""AURA Plugin Example — System Info plugin."""

from __future__ import annotations

import platform
import time
from typing import Any, Dict, Optional

from aura_plugin_system import AuraPlugin


class SystemInfoPlugin(AuraPlugin):
    def get_name(self) -> str:
        return "System Info"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Real-time system information and diagnostics"
    
    def get_author(self) -> str:
        return "AURA"
    
    def on_load(self) -> None:
        self._start_time = time.time()
        print(f"[PLUGIN] {self.get_name()} loaded!")
    
    def on_chat_message(self, message: str) -> Optional[str]:
        lower = message.lower()
        if any(g in lower for g in ["cpu", "processor", "procesador"]):
            return self._get_cpu_info()
        if any(g in lower for g in ["ram", "memory", "memoria"]):
            return self._get_memory_info()
        if any(g in lower for g in ["disk", "storage", "disco"]):
            return self._get_disk_info()
        if any(g in lower for g in ["system", "sistema", "info"]):
            return self._get_system_info()
        return None
    
    def _get_system_info(self) -> str:
        uptime = int(time.time() - self._start_time)
        return f"System: {platform.system()} {platform.release()} | Uptime: {uptime}s | Python: {platform.python_version()}"
    
    def _get_cpu_info(self) -> str:
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            return f"CPU: {cpu_count} cores | Usage: {cpu_percent}%"
        except ImportError:
            return "CPU info: psutil not installed"
    
    def _get_memory_info(self) -> str:
        try:
            import psutil
            mem = psutil.virtual_memory()
            return f"RAM: {mem.total / (1024**3):.1f} GB total | {mem.percent}% used | {mem.available / (1024**3):.1f} GB available"
        except ImportError:
            return "Memory info: psutil not installed"
    
    def _get_disk_info(self) -> str:
        try:
            import psutil
            disk = psutil.disk_usage('/')
            return f"Disk: {disk.total / (1024**3):.1f} GB total | {disk.percent}% used | {disk.free / (1024**3):.1f} GB free"
        except ImportError:
            return "Disk info: psutil not installed"
