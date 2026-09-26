"""Ensambla el frontend web de AURA moviendo archivos sueltos de Downloads."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT.parent
WEB_DASHBOARD = ROOT / "frontend" / "web_dashboard"

STRUCTURE = [
    WEB_DASHBOARD / "src" / "components",
]

MOVES = {
    DOWNLOADS / "package": WEB_DASHBOARD / "package.json",
    DOWNLOADS / "vite.config": WEB_DASHBOARD / "vite.config.js",
    DOWNLOADS / "index (2)": WEB_DASHBOARD / "index.html",
    DOWNLOADS / "main.jsx": WEB_DASHBOARD / "src" / "main.jsx",
    DOWNLOADS / "App.jsx": WEB_DASHBOARD / "src" / "App.jsx",
    DOWNLOADS / "App.css": WEB_DASHBOARD / "src" / "App.css",
    DOWNLOADS / "globals.css": WEB_DASHBOARD / "src" / "globals.css",
    DOWNLOADS / "useWebSocket": WEB_DASHBOARD / "src" / "useWebSocket.jsx",
    DOWNLOADS / "NucleusCanvas.jsx": WEB_DASHBOARD / "src" / "components" / "NucleusCanvas.jsx",
    DOWNLOADS / "SynapticGraph.jsx": WEB_DASHBOARD / "src" / "components" / "SynapticGraph.jsx",
    DOWNLOADS / "ReactorMatrix.jsx": WEB_DASHBOARD / "src" / "components" / "ReactorMatrix.jsx",
    DOWNLOADS / "ReactorMatrix.css": WEB_DASHBOARD / "src" / "components" / "ReactorMatrix.css",
    DOWNLOADS / "TacticalChat.jsx": WEB_DASHBOARD / "src" / "components" / "TacticalChat.jsx",
    DOWNLOADS / "HexColorPicker.jsx": WEB_DASHBOARD / "src" / "components" / "HexColorPicker.jsx",
    DOWNLOADS / "Telemetry.jsx": WEB_DASHBOARD / "src" / "components" / "Telemetry.jsx",
}


def ensure_dirs() -> None:
    for d in STRUCTURE:
        d.mkdir(parents=True, exist_ok=True)


def move_files() -> None:
    for src, dst in MOVES.items():
        if not src.exists():
            print(f"[WARN] No existe: {src}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"[OK] {src.name} -> {dst}")


def main() -> None:
    print("Ensamblando frontend web de AURA...")
    ensure_dirs()
    move_files()
    print("Listo.")


if __name__ == "__main__":
    main()
