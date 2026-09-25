import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path")
    content = params.get("content", "")
    if not path:
        return {"written": False, "error": "path vacío"}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"written": True, "path": path, "bytes": len(content.encode("utf-8"))}
    except Exception as e:
        return {"written": False, "error": str(e)}
