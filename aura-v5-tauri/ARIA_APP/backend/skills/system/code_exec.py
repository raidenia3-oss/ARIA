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
    elif action == "eval":
        return _eval_code(params)
    return {"error": f"Unknown action: {action}"}


def _execute(params: Dict[str, Any]) -> Dict[str, Any]:
    code = params.get("code", "")
    timeout = params.get("timeout", 10)
    if not code:
        return {"error": "code requerido"}
    try:
        start = time.time()
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok",
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
            "duration_ms": duration,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Code execution timed out", "timeout": timeout}
    except Exception as e:
        return {"error": str(e)}


def _eval_code(params: Dict[str, Any]) -> Dict[str, Any]:
    code = params.get("code", "")
    timeout = params.get("timeout", 5)
    if not code:
        return {"error": "code requerido"}
    try:
        start = time.time()
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
        )
        duration = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok",
            "result": result.stdout[:2000],
            "error": result.stderr[:500] if result.stderr else None,
            "duration_ms": duration,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "timeout": timeout}
    except Exception as e:
        return {"error": str(e)}
