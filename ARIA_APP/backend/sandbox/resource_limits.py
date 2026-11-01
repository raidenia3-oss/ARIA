from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResourceLimits:
    timeout_seconds: int = 30
    max_output_chars: int = 5000
    max_memory_mb: int = 512
    allow_network: bool = False
    allow_fs_write: bool = True
    sandbox_dir_only: bool = True
