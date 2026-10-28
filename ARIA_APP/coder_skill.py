"""ARIA coder skill: escribe codigo a archivo bajo path_guard (fail-closed)."""
import os


def write_code(path, code, overwrite=False):
    try:
        from path_guard import resolve_allowed, PathGuardError
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    try:
        resolved = resolve_allowed(path, "write")
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    path = str(resolved)
    if os.path.exists(path) and not overwrite:
        return {"status": "error", "error": "archivo existe; pasa overwrite=True para reemplazar"}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return {"status": "ok", "path": path, "bytes": len(code.encode("utf-8"))}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def read_code(path):
    try:
        from path_guard import resolve_allowed
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    try:
        resolved = resolve_allowed(path, "read")
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    path = str(resolved)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return {"status": "ok", "path": path, "content": f.read()}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
