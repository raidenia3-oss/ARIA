import os
import subprocess
import sys
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    app = (params.get("app") or "").strip()
    if not app:
        return {"opened": None, "status": "no app specified"}
    try:
        if sys.platform == "win32":
            targets = {
                "notepad": "notepad.exe",
                "bloc de notas": "notepad.exe",
                "calc": "calc.exe",
                "calculadora": "calc.exe",
                "explorer": "explorer.exe",
                "edge": "msedge.exe",
                "chrome": "chrome.exe",
                "cmd": "cmd.exe",
                "terminal": "wt.exe",
                "powershell": "powershell.exe",
            }
            exe = targets.get(app.lower(), app)
            subprocess.Popen(["cmd", "/c", "start", "", exe], shell=False)
            return {"opened": exe, "status": "launched"}
        subprocess.Popen([app])
        return {"opened": app, "status": "launched"}
    except Exception as e:
        return {"opened": app, "status": "error", "error": str(e)}
