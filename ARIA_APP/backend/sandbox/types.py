from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SandboxConfig:
    work_dir: str = ""
    timeout: int = 30
    max_output_chars: int = 5000
    allow_network: bool = False
    allow_fs_write: bool = True
    env_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    ok: bool
    sandbox_id: str
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    elapsed_ms: int = 0
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        limit = self.meta.get("max_output_chars", 5000)
        return {
            "ok": self.ok,
            "sandbox_id": self.sandbox_id,
            "command": self.command,
            "stdout": self.stdout[:limit] if self.stdout else "",
            "stderr": self.stderr[:limit] if self.stderr else "",
            "returncode": self.returncode,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
            "meta": self.meta,
        }


@dataclass
class SandboxEntry:
    sandbox_id: str
    config: SandboxConfig
    created_at: datetime
    status: str = "idle"
    last_result: Optional[SandboxResult] = None
