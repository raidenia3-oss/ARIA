from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


class FileSystemJail:
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir).resolve()

    def is_allowed(self, path: str) -> bool:
        try:
            target = Path(path).resolve()
        except Exception:
            return False
        try:
            target.relative_to(self.root)
            return True
        except ValueError:
            return False

    def safe_join(self, *parts: str) -> Path:
        joined = self.root.joinpath(*parts)
        resolved = joined.resolve()
        if not self._is_within(resolved):
            raise PermissionError(f"ruta fuera del sandbox: {joined}")
        return resolved

    def _is_within(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            return False

    def ensure_dir(self, path: str) -> Path:
        p = self.safe_join(path)
        p.mkdir(parents=True, exist_ok=True)
        return p
