import os
import sys
from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    checks = {}
    try:
        from backend.memory import long_term

        checks["memory_long_term"] = "ok"
    except Exception as e:
        checks["memory_long_term"] = str(e)
    try:
        from backend.skills.registry import SkillRegistry

        registry = SkillRegistry()
        checks["skills"] = len(registry.list())
    except Exception as e:
        checks["skills"] = str(e)
    checks["python"] = sys.version.split()[0]
    checks["cwd"] = os.getcwd()
    checks["data_dir"] = os.environ.get("ARIA_DATA_DIR", "")
    return {"status": "ok", "checks": checks}
