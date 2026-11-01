from __future__ import annotations

from typing import Any, Dict

from .project import run as project_run


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    return project_run(dict(params))
