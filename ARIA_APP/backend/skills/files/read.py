import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path")
    if not path:
        return {"read": False, "error": "path vacío"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return {
            "read": True,
            "path": path,
            "content": text[:4000],
            "bytes": len(text.encode("utf-8")),
        }
    except Exception as e:
        return {"read": False, "error": str(e)}
