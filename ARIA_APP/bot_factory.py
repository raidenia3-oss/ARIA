"""Fabrica de bots para ARIA: crea bots Python simples y los lanza como subprocesos."""
import os
import subprocess
import sys

BOTS_DIR = os.path.join(os.path.dirname(__file__), "bots")


def create_bot(name: str, purpose: str = "general") -> dict:
    os.makedirs(BOTS_DIR, exist_ok=True)
    safe = "".join(c for c in name if c.isalnum() or c in "_-").strip() or "bot"
    path = os.path.join(BOTS_DIR, f"{safe}.py")
    code = (
        "# Bot creado por ARIA\n"
        f"# Proposito: {purpose}\n"
        "import time, sys\n"
        "print('Bot %s iniciado (proposito: %s)' % (name if False else '%s', '%s'))\n"
        % (safe, purpose)
        + "while True:\n"
        "    print('tick')\n"
        "    time.sleep(5)\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return {"status": "ok", "name": safe, "path": path}


def launch_bot(name: str) -> dict:
    safe = "".join(c for c in name if c.isalnum() or c in "_-").strip() or "bot"
    path = os.path.join(BOTS_DIR, f"{safe}.py")
    if not os.path.exists(path):
        return {"status": "error", "error": "bot no existe"}
    try:
        proc = subprocess.Popen([sys.executable, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "ok", "pid": proc.pid, "name": safe}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def list_bots() -> list:
    if not os.path.exists(BOTS_DIR):
        return []
    return [f for f in os.listdir(BOTS_DIR) if f.endswith(".py")]
EOF