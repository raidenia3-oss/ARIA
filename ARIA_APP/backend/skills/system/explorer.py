import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    if action == "execute":
        return _execute(params)
    elif action == "list_files":
        return _list_files(params)
    elif action == "read_file":
        return _read_file(params)
    elif action == "write_file":
        return _write_file(params)
    elif action == "get_tree":
        return _get_tree(params)
    return {"error": f"Unknown action: {action}"}


def _execute(params: Dict[str, Any]) -> Dict[str, Any]:
    command = params.get("command", "")
    timeout = params.get("timeout", 30)
    safe_mode = params.get("safe_mode", True)
    if safe_mode and command:
        blocked = ["rm -rf", "del /", "format", "shutdown", "regedit", "diskpart", "mkfs", "fdisk"]
        cmd_lower = command.lower()
        for b in blocked:
            if b in cmd_lower:
                return {"error": f"Command blocked for safety: {b}", "command": command}
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        return {
            "status": "ok",
            "command": command,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
            "duration_ms": round((result.duration * 1000) if hasattr(result, 'duration') else 0, 1),
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out", "command": command, "timeout": timeout}
    except Exception as e:
        return {"error": str(e), "command": command}


def _list_files(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", ".")
    max_depth = params.get("max_depth", 1)
    try:
        base = os.path.abspath(path)
        if not os.path.exists(base):
            return {"error": f"Path not found: {base}"}
        if max_depth == 0:
            items = []
            for entry in sorted(os.listdir(base)):
                full = os.path.join(base, entry)
                items.append({
                    "name": entry,
                    "type": "dir" if os.path.isdir(full) else "file",
                    "size": os.path.getsize(full) if os.path.isfile(full) else 0,
                })
            return {"status": "ok", "path": base, "items": items, "count": len(items)}
        items = []
        for root, dirs, files in os.walk(base):
            depth = root.count(os.sep) - base.count(os.sep)
            if depth >= max_depth:
                dirs.clear()
                continue
            for d in sorted(dirs):
                items.append({"name": os.path.join(root, d), "type": "dir", "size": 0})
            for f in sorted(files):
                full = os.path.join(root, f)
                items.append({"name": full, "type": "file", "size": os.path.getsize(full)})
        return {"status": "ok", "path": base, "items": items, "count": len(items)}
    except Exception as e:
        return {"error": str(e)}


def _read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", "")
    max_lines = params.get("max_lines", 100)
    encoding = params.get("encoding", "utf-8")
    if not path:
        return {"error": "path requerido"}
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            lines = f.readlines()[:max_lines]
        return {
            "status": "ok",
            "path": path,
            "total_lines": len(lines),
            "content": "".join(lines),
            "encoding": encoding,
        }
    except Exception as e:
        return {"error": str(e)}


def _write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", "")
    content = params.get("content", "")
    encoding = params.get("encoding", "utf-8")
    if not path:
        return {"error": "path requerido"}
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            f.write(content)
        return {"status": "ok", "path": path, "bytes_written": len(content.encode(encoding))}
    except Exception as e:
        return {"error": str(e)}


def _get_tree(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", ".")
    max_depth = params.get("max_depth", 2)
    try:
        base = os.path.abspath(path)
        lines = []
        _build_tree(base, "", 0, max_depth, lines)
        return {"status": "ok", "path": base, "tree": "\n".join(lines)}
    except Exception as e:
        return {"error": str(e)}


def _build_tree(base: str, prefix: str, depth: int, max_depth: int, lines: List[str]) -> None:
    if depth > max_depth:
        return
    try:
        entries = sorted(os.listdir(base))
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            full = os.path.join(base, entry)
            is_dir = os.path.isdir(full)
            suffix = "/" if is_dir else ""
            lines.append(f"{prefix}{connector}{entry}{suffix}")
            if is_dir and depth < max_depth:
                extension = "    " if is_last else "│   "
                _build_tree(full, prefix + extension, depth + 1, max_depth, lines)
    except PermissionError:
        lines.append(f"{prefix}└── [Permission Denied]")
