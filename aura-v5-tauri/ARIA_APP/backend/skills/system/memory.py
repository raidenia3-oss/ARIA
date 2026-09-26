import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    base = os.path.dirname(__file__)
    memory_dir = os.path.abspath(os.path.join(base, "../../memory"))
    os.makedirs(memory_dir, exist_ok=True)
    files = sorted([f for f in os.listdir(memory_dir) if f.endswith(".json")])
    query = params.get("query", "")
    matches = []
    if query:
        for fname in files:
            path = os.path.join(memory_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                if query.lower() in text.lower():
                    matches.append(fname)
            except Exception:
                pass
    return {"query": query, "matches": len(matches), "files": matches[:10]}
