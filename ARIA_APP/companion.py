# -*- coding: utf-8 -*-
"""Companion local de ARIA: extension del dispositivo (sin red, sin puertos).

Se ejecuta como proceso hijo comunicando por stdin/stdout. Solo capacidades
locales de lectura por defecto; toda accion pasa por PermissionEngine.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time


def _collect_info() -> dict:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "python": platform.python_version(),
        "cwd": os.getcwd(),
        "pid": os.getpid(),
        "time": time.time(),
    }


def main() -> None:
    # Protocolo: una linea JSON por stdin -> una linea JSON por stdout.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            req = {"action": "ping"}
        action = req.get("action", "ping")
        if action == "ping":
            resp = {"ok": True, "pong": True, "info": _collect_info()}
        elif action == "info":
            resp = {"ok": True, "info": _collect_info()}
        elif action == "echo":
            resp = {"ok": True, "echo": req.get("data")}
        else:
            resp = {"ok": False, "error": "accion no permitida: " + str(action)}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()