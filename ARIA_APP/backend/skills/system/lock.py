import os
import subprocess
import sys
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "lock")
    try:
        if sys.platform == "win32":
            if action == "lock":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                return {"action": "lock", "status": "ok"}
        return {"action": action, "status": "unsupported"}
    except Exception as e:
        return {"action": action, "status": "error", "error": str(e)}
