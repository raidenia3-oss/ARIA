from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fs_jail import FileSystemJail
from .types import SandboxConfig, SandboxEntry, SandboxResult


class SkillRunner:
    def __init__(self, sandbox_dir: str, logic_engine: Any) -> None:
        self.sandbox_dir = Path(sandbox_dir).resolve()
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.jail = FileSystemJail(str(self.sandbox_dir))
        self.logic_engine = logic_engine
        self.entries: Dict[str, SandboxEntry] = {}

    def _new_id(self) -> str:
        return "sandbox_skill_" + uuid.uuid4().hex[:12]

    def run_skill(self, skill_name: str, params: Dict[str, Any], config: SandboxConfig) -> SandboxResult:
        sandbox_id = self._new_id()
        entry = SandboxEntry(sandbox_id=sandbox_id, config=config,
                             created_at=datetime.now(), status="running")
        self.entries[sandbox_id] = entry

        start = time.time()
        result = SandboxResult(ok=False, sandbox_id=sandbox_id,
                               command=f"skill:{skill_name}")
        try:
            if not hasattr(self.logic_engine, "_handle_skill"):
                raise RuntimeError("logic_engine no expone _handle_skill")
            data = {"skill": skill_name, "params": params}
            out = self.logic_engine._handle_skill(data)
            result.stdout = str(out)
            result.ok = out.get("status") == "ok"
            result.returncode = 0 if result.ok else 1
            entry.status = "done" if result.ok else "error"
        except Exception as exc:
            result.error = str(exc)
            result.stderr = str(exc)
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
