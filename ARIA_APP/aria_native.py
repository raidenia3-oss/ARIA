r"""ARIA OS Native — entry point.

Ejecuta ARIA como aplicación de escritorio nativa:
- UI con PyQt5 (ventana real, no navegador)
- Motor de lógica en mismo proceso (llamada directa, no IPC de red)
- IA local vía Ollama (localhost:11434) o fallback rule-based
- Cero puertos TCP abiertos, cero servidor HTTP, cero dependencia de red

Uso:
    .venv\Scripts\python.exe ARIA_APP\aria_native.py

Build (PyInstaller, un solo archivo .exe):
    .venv\Scripts\python.exe -m PyInstaller --onefile --windowed ^
      --name "ARIA OS" ^
      --add-data "ARIA_APP\.env;ARIA_APP" ^
      --hidden-import native_core ^
      --hidden-import PyQt5 --hidden-import PyQt5.QtWidgets ^
      --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtGui ^
      --noconfirm ARIA_APP\aria_native.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Asegurar que ARIA_APP y el padre estén en el path
ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
for p in (str(ARIA_APP), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Cargar variables de entorno antes de importar native_core
from dotenv import load_dotenv
load_dotenv(str(ARIA_APP / ".env"))

from native_core import main

if __name__ == "__main__":
    sys.exit(main())
