import os
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", ".")
    try:
        entries = []
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            entries.append({"name": entry, "is_dir": os.path.isdir(full)})
        return {"path": path, "entries": entries[:50], "count": len(entries)}
    except Exception as e:
        return {"path": path, "entries": [], "error": str(e)}
