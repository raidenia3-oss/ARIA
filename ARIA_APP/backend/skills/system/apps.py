import os
import subprocess
import sys
from typing import Any, Dict, List


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(["tasklist", "/fo", "csv", "/nh"], text=True, timeout=10)
            lines = [line.strip().strip('"') for line in out.splitlines() if line.strip()]
            apps = []
            for line in lines[:50]:
                parts = line.split('","')
                if len(parts) >= 2:
                    apps.append({"name": parts[0], "pid": parts[1]})
            return {"apps": apps, "count": len(apps)}
        return {"apps": [], "error": "unsupported platform"}
    except Exception as e:
        return {"apps": [], "error": str(e)}
