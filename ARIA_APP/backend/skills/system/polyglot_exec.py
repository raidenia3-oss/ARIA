import shutil
import subprocess
import sys
import time
from typing import Any, Dict

LANGS = {
    "python": [sys.executable, "-c"],
    "javascript": ["node", "-e"],
    "typescript": ["npx", "ts-node", "-e"],
    "go": ["go", "run"],
    "rust": ["rustc", "--edition", "2021"],
    "c": ["gcc"],
    "cpp": ["g++"],
    "java": ["java"],
    "ruby": ["ruby", "-e"],
    "php": ["php", "-r"],
    "perl": ["perl", "-e"],
    "lua": ["lua", "-e"],
    "r": ["Rscript", "-e"],
    "shell": ["bash", "-c"],
}


def available() -> Dict[str, bool]:
    out = {}
    for lang, cmd in LANGS.items():
        out[lang] = shutil.which(cmd[0]) is not None
    return out


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    lang = str(params.get("language", "")).lower()
    code = str(params.get("code", ""))
    timeout = int(params.get("timeout", 10))
    if lang not in LANGS:
        return {"status": "error", "error": "lenguaje no soportado", "supported": list(LANGS)}
    if not code:
        return {"status": "error", "error": "code requerido"}
    exe = LANGS[lang][0]
    if shutil.which(exe) is None:
        return {"status": "error", "error": f"{exe} no instalado", "language": lang}
    cmd = LANGS[lang] + [code]
    if lang in {"go", "rust", "c", "cpp", "java"}:
        return {"status": "error", "error": "lenguaje requiere archivo temporal; no implementado aun", "language": lang}
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok",
            "language": lang,
            "stdout": result.stdout[:3000],
            "stderr": result.stderr[:1000],
            "returncode": result.returncode,
            "duration_ms": round((time.time() - start) * 1000, 1),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout", "language": lang}
    except Exception as e:
        return {"status": "error", "error": str(e), "language": lang}
