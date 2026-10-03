import os
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.expanduser("~")).percent
        return {
            "cpu": f"{cpu}%",
            "memory": f"{mem}%",
            "disk": f"{disk}%",
            "backend": "running",
            "data_source": "measured",
        }
    except Exception as e:
        # Honestidad: sin psutil no hay medicion; devolver "ok" afirmaria el
        # sistema sin base. Contrato v6/axum-poc: dato no medido -> valor null
        # + data_source "unavailable". "backend": "running" es un hecho: si esta
        # skill responde, el proceso backend esta vivo.
        return {
            "cpu": None,
            "memory": None,
            "disk": None,
            "backend": "running",
            "data_source": "unavailable",
            "detail": f"not measured: psutil unavailable or measurement failed ({e})",
            "error": str(e),
        }
