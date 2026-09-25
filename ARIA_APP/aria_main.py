"""ARIA OS v4.0 — Desktop Standalone Entry Point.
Spawns UI process + Logic process, connected via IPC pipes.
Zero HTTP, zero servers, zero ports."""

from __future__ import annotations

import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from dotenv import load_dotenv

ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
load_dotenv(str(ARIA_APP / ".env"))

os.environ.setdefault("ARIA_SYSTEM_PROMPT",
    "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español.")


def _import_desktop():
    sys.path.insert(0, str(ARIA_APP))
    # Ensure frozen-mode detection works inside the EXE
    sys.frozen = True
    if not hasattr(sys, "_MEIPASS"):
        sys._MEIPASS = str(ARIA_APP)
    from desktop_ui import run_desktop
    run_desktop()


def main():
    print("[ARIA v4.0] Desktop Standalone — Sin HTTP, Sin servidores", flush=True)

    if "ARIA_LOGIC_PROCESS" in os.environ:
        # Estamos en el proceso de lógica
        import aria_logic_engine
        aria_logic_engine.main()
        return

    # Proceso principal: lanza UI que a su vez lanza Logic via IPC
    os.environ["ARIA_LOGIC_PROCESS"] = "1"

    print("[ARIA v4.0] Iniciando UI + Logic (IPC pipes)...", flush=True)
    start = time.time()
    _import_desktop()
    elapsed = time.time() - start
    print(f"[ARIA v4.0] Cerró tras {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
