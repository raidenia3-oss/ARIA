# GitLens: aprender proyecto de GitHub/sitio web - fail-closed
from __future__ import annotations
from typing import Any, Dict
import os


class GitLens:
    def __init__(self) -> None:
        self.learned: Dict[str, Any] = {}

    def learn_repo(self, path: str) -> Dict[str, Any]:
        if not path or not os.path.isdir(path):
            return {"status": "invalid"}
        files = []
        for root, _, fs in os.walk(path):
            for f in fs:
                files.append(os.path.join(root, f))
        self.learned[path] = {"files": len(files), "sample": files[:20]}
        return {"status": "learned", "repo": path, "files": len(files)}

    def status(self) -> Dict[str, Any]:
        return {"learned": list(self.learned.keys()), "count": len(self.learned)}


gitlens = GitLens()
