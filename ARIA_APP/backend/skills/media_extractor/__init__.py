from __future__ import annotations

from typing import Any, Dict

from .extractor import run as extractor_run


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    return extractor_run(dict(params))
