# Git/GitHub integrator - fail-closed, no invented data
from __future__ import annotations
import os
import subprocess
from typing import Any, Dict, Optional


class GitIntegrator:
    def __init__(self) -> None:
        pass

    def clone(self, url: str, dest: str, shallow: bool = True) -> Dict[str, Any]:
        if not url or not dest:
            return {"status": "invalid"}
        try:
            cmd = ["git", "clone"]
            if shallow:
                cmd.extend(["--depth", "1"])
            cmd.extend([url, dest])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {"status": "ok" if r.returncode == 0 else "error", "returncode": r.returncode, "stdout": r.stdout[-500:], "stderr": r.stderr[-500:]}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def pull(self, repo_path: str) -> Dict[str, Any]:
        if not repo_path or not os.path.isdir(repo_path):
            return {"status": "invalid"}
        try:
            r = subprocess.run(["git", "pull"], cwd=repo_path, capture_output=True, text=True, timeout=120)
            return {"status": "ok" if r.returncode == 0 else "error", "returncode": r.returncode}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def status(self, repo_path: str) -> Dict[str, Any]:
        if not repo_path or not os.path.isdir(repo_path):
            return {"status": "invalid"}
        try:
            r = subprocess.run(["git", "log", "--oneline", "-5"], cwd=repo_path, capture_output=True, text=True, timeout=30)
            return {"status": "ok", "log": r.stdout}
        except Exception as e:
            return {"status": "error", "error": str(e)}


git_integrator = GitIntegrator()
