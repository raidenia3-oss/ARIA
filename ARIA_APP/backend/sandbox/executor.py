from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fs_jail import FileSystemJail
from .resource_limits import ResourceLimits
from .types import SandboxConfig, SandboxEntry, SandboxResult


class CodeExecutor:
    def __init__(self, sandbox_dir: str) -> None:
        self.sandbox_dir = Path(sandbox_dir).resolve()
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.jail = FileSystemJail(str(self.sandbox_dir))
        self.entries: Dict[str, SandboxEntry] = {}

    def _new_id(self) -> str:
        return "sandbox_" + uuid.uuid4().hex[:12]

    def exec_code(self, code: str, config: SandboxConfig) -> SandboxResult:
        sandbox_id = self._new_id()
        entry = SandboxEntry(sandbox_id=sandbox_id, config=config,
                             created_at=datetime.now(), status="running")
        self.entries[sandbox_id] = entry

        start = time.time()
        work_dir = str(self.sandbox_dir / sandbox_id)
        Path(work_dir).mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        env.update(config.env_vars)
        if not config.allow_network:
            env.pop("HTTP_PROXY", None)
            env.pop("HTTPS_PROXY", None)
            env.pop("http_proxy", None)
            env.pop("https_proxy", None)

        script_path = Path(work_dir) / "script.py"
        script_path.write_text(code, encoding="utf-8")

        result = SandboxResult(ok=False, sandbox_id=sandbox_id,
                               command=code[:200])
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True, text=True, timeout=config.timeout,
                cwd=work_dir, env=env,
            )
            result.stdout = proc.stdout or ""
            result.stderr = proc.stderr or ""
            result.returncode = proc.returncode
            result.ok = proc.returncode == 0
            entry.status = "done" if result.ok else "error"
        except subprocess.TimeoutExpired:
            result.error = f"timeout tras {config.timeout}s"
            entry.status = "error"
        except Exception as exc:
            result.error = str(exc)
            entry.status = "error"
        finally:
            result.elapsed_ms = int((time.time() - start) * 1000)
            entry.last_result = result

        return result

    def get_status(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        entry = self.entries.get(sandbox_id)
        if not entry:
            return None
        return {
            "sandbox_id": entry.sandbox_id,
            "status": entry.status,
            "created_at": entry.created_at.isoformat(),
            "last_result": entry.last_result.to_dict() if entry.last_result else None,
        }

    def list_sandboxes(self) -> List[Dict[str, Any]]:
        return [self.get_status(sid) for sid in self.entries]  # type: ignore[arg-type]

    def stop(self, sandbox_id: str) -> bool:
        entry = self.entries.get(sandbox_id)
        if not entry:
            return False
        entry.status = "stopped"
        return True
