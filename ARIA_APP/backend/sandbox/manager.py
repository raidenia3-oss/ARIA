from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .executor import CodeExecutor
from .skill_runner import SkillRunner
from .types import SandboxConfig, SandboxResult


class SandboxManager:
    def __init__(self, logic_engine: Any, base_dir: str) -> None:
        self.logic_engine = logic_engine
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.code_exec = CodeExecutor(str(self.base_dir / "code"))
        self.skill_runner = SkillRunner(str(self.base_dir / "skills"), logic_engine)

    def exec_code(self, code: str, config: SandboxConfig) -> SandboxResult:
        return self.code_exec.exec_code(code, config)

    def run_skill(self, skill_name: str, params: Dict[str, Any], config: SandboxConfig) -> SandboxResult:
        return self.skill_runner.run_skill(skill_name, params, config)

    def status(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        r = self.code_exec.get_status(sandbox_id)
        if r:
            return r
        return self.skill_runner.get_status(sandbox_id)

    def list_all(self) -> Dict[str, Any]:
        return {
            "code": self.code_exec.list_sandboxes(),
            "skills": self.skill_runner.list_sandboxes(),
        }

    def stop(self, sandbox_id: str) -> bool:
        return self.code_exec.stop(sandbox_id) or self.skill_runner.stop(sandbox_id)
