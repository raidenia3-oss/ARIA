from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any, Dict


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


def _ctypes_status() -> Dict[str, Any]:
    sps = SYSTEM_POWER_STATUS()
    ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps))
    if not ok:
        return {"error": "GetSystemPowerStatus failed", "data_source": "unavailable"}
    no_battery = bool(sps.BatteryFlag & 128)
    return {
        "has_battery": not no_battery,
        "on_ac": sps.ACLineStatus == 1,
        "ac_line_status_raw": sps.ACLineStatus,
        "battery_flag": sps.BatteryFlag,
        "percent": sps.BatteryLifePercent if sps.BatteryLifePercent != 255 else None,
        "charging": bool(sps.BatteryFlag & 8),
        "source": "GetSystemPowerStatus",
        "data_source": "measured",
    }


def _psutil_status() -> Dict[str, Any]:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return {"has_battery": False, "on_ac": True,
                    "percent": None, "source": "psutil", "data_source": "measured"}
        return {
            "has_battery": True,
            "on_ac": bool(b.power_plugged),
            "percent": round(b.percent, 1),
            "secs_left": b.secsleft
            if b.secsleft not in (psutil.POWER_TIME_UNKNOWN, psutil.POWER_TIME_UNLIMITED)
            else None,
            "source": "psutil",
            "data_source": "measured",
        }
    except Exception as exc:
        return {"error": str(exc), "source": "psutil", "data_source": "unavailable"}


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "status")
    if action == "status":
        primary = _ctypes_status()
        fallback = _psutil_status()
        return {
            "status": "ok",
            "skill": "power",
            "primary": primary,
            "fallback": fallback,
            "on_ac": primary.get("on_ac", fallback.get("on_ac")),
            "has_battery": primary.get("has_battery", fallback.get("has_battery")),
        }
    if action == "can_wake_on_ac":
        return {
            "status": "ok",
            "skill": "power",
            "note": "El encendido al conectar cargador depende del BIOS/UEFI (opcion 'Wake on AC' / 'Restore on AC Power Loss'). ARIA solo detecta el estado y puede enviar WoL a otras PCs.",
            "data_source": "documentation",
        }
    return {"error": f"accion desconocida: {action}"}
