"""ARIA OS v4.0 — Desktop Standalone Entry Point.
Un solo proceso, 100% local. Cero HTTP, cero servidores, cero puertos,
cero comandos de shell, cero subprocess, cero localhost.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
load_dotenv(str(ARIA_APP / ".env"))

os.environ.setdefault("ARIA_SYSTEM_PROMPT",
    "Eres ARIA, asistente virtual personal estilo Jarvis. "
    "Respondes en español, operas 100% en local, sin servidores ni internet.")


def main():
    print("[ARIA v4.0] Desktop Standalone — 100% Local, Sin HTTP, Sin Servidores", flush=True)

    sys.path.insert(0, str(ARIA_APP))
    from desktop_ui import run_desktop
    run_desktop()


if __name__ == "__main__":
    main()
