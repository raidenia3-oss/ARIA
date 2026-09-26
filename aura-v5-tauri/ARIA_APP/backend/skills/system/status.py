import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.expanduser("~")).percent
        return {"cpu": f"{cpu}%", "memory": f"{mem}%", "disk": f"{disk}%", "backend": "running"}
    except Exception as e:
        return {"cpu": "ok", "memory": "ok", "disk": "ok", "backend": "running", "error": str(e)}
