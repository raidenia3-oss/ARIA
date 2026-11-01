from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _adb_path() -> Optional[str]:
    p = shutil.which("adb")
    if p:
        return p
    for cand in (
        r"C:\Android\Sdk\platform-tools\adb.exe",
        r"C:\platform-tools\adb.exe",
        os.path.expanduser(r"~\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    ):
        if os.path.exists(cand):
            return cand
    return None


def _run(args: List[str], timeout: int = 30) -> Dict[str, Any]:
    adb = _adb_path()
    if not adb:
        return {"status": "error", "error": "adb no encontrado. Instala Android platform-tools y agrega a PATH."}
    try:
        out = subprocess.run([adb] + args, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok" if out.returncode == 0 else "error",
            "returncode": out.returncode,
            "stdout": out.stdout.strip(),
            "stderr": out.stderr.strip(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def status(params: Dict[str, Any]) -> Dict[str, Any]:
    adb = _adb_path()
    return {"adb": adb, "available": bool(adb)}


def devices(params: Dict[str, Any]) -> Dict[str, Any]:
    return _run(["devices", "-l"])


def tcpip(params: Dict[str, Any]) -> Dict[str, Any]:
    port = int(params.get("port", 5555))
    return _run(["tcpip", str(port)])


def connect(params: Dict[str, Any]) -> Dict[str, Any]:
    ip = params.get("ip") or params.get("host")
    if not ip:
        return {"status": "error", "error": "falta ip"}
    port = int(params.get("port", 5555))
    return _run(["connect", f"{ip}:{port}"])


def disconnect(params: Dict[str, Any]) -> Dict[str, Any]:
    target = params.get("target")
    if target:
        return _run(["disconnect", target])
    return _run(["disconnect"])


def install(params: Dict[str, Any]) -> Dict[str, Any]:
    apk = params.get("apk") or params.get("path")
    if not apk or not os.path.exists(apk):
        return {"status": "error", "error": f"apk no encontrado: {apk}"}
    return _run(["install", "-r", apk], timeout=120)


def launch(params: Dict[str, Any]) -> Dict[str, Any]:
    pkg = params.get("package") or params.get("pkg")
    if not pkg:
        return {"status": "error", "error": "falta package"}
    activity = params.get("activity")
    if activity:
        return _run(["shell", "am", "start", "-n", f"{pkg}/{activity}"])
    return _run(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])


def open_as_desktop(params: Dict[str, Any]) -> Dict[str, Any]:
    url = params.get("url")
    if not url:
        return {"status": "error", "error": "falta url"}
    name = params.get("name", "ARIA App")
    # Use Edge/Chrome app mode (no server, local browser)
    for exe in (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ):
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, f"--app={url}", f"--window-name={name}"])
                return {"status": "ok", "browser": exe, "url": url}
            except Exception as e:
                return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "no se encontro Edge/Chrome"}


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = (params.get("action") or "").lower()
    if action == "status":
        return status(params)
    if action == "devices":
        return devices(params)
    if action == "tcpip":
        return tcpip(params)
    if action == "connect":
        return connect(params)
    if action == "disconnect":
        return disconnect(params)
    if action == "install":
        return install(params)
    if action == "launch":
        return launch(params)
    if action == "desktop":
        return open_as_desktop(params)
    return {"status": "error", "error": f"accion desconocida: {action}"}
