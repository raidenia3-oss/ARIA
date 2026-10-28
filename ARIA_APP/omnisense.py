"""ARIA OMNISENSE: percepcion unificada RF + Ojos de Dios + magnetico."""
import json


def omni_sense(va_state=None, bbox=None):
    result = {"version": "ARIA OMNISENSE v1", "layers": {}}
    # RF
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from aria_va_core import VirtualAssistant
    except Exception:
        VirtualAssistant = None
    # We avoid instantiating VA; call modules directly
    try:
        import subprocess, re
        out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], text=True, stderr=subprocess.DEVNULL, timeout=10)
        signal = None
        for line in out.splitlines():
            line = line.strip()
            if line.lower().startswith("signal"):
                m = re.search(r"(\d+)", line)
                if m:
                    signal = int(m.group(1))
        result["layers"]["rf"] = {"signal": signal, "presence": "posible" if signal is not None and signal < 60 else "normal"}
    except Exception as exc:
        result["layers"]["rf"] = {"error": str(exc)}
    # Eyes
    try:
        from eyes_of_god import snapshot
        bb = bbox or [-90, -180, 90, 180]
        result["layers"]["eyes"] = snapshot(*bb)
    except Exception as exc:
        result["layers"]["eyes"] = {"error": str(exc)}
    # Magnetic
    result["layers"]["magnetic"] = {"available": False, "reason": "sin sensor"}
    return result
