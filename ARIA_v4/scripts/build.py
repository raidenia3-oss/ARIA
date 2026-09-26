"""ARIA OS v4.0 — Build script."""
import subprocess
import sys
from pathlib import Path


def build():
    print("[Build] Building ARIA OS v4.0...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--name", "AURA OS",
        "--add-data", "AURA_APP/frontend;frontend",
        "--add-data", "ai_providers.py;.",
        "--hidden-import", "ai_providers",
        "--hidden-import", "backend.skills",
        "--hidden-import", "backend.skills.registry",
        "--hidden-import", "backend.skills.system",
        "--hidden-import", "backend.skills.system.status",
        "--hidden-import", "backend.skills.system.time",
        "--hidden-import", "backend.skills.system.ping",
        "--hidden-import", "backend.skills.system.scan",
        "--hidden-import", "backend.skills.system.whois",
        "--hidden-import", "backend.skills.system.open",
        "--hidden-import", "backend.skills.system.volume",
        "--hidden-import", "backend.skills.system.lock",
        "--hidden-import", "backend.skills.system.apps",
        "--hidden-import", "backend.skills.system.screenshot",
        "--hidden-import", "backend.skills.system.memory",
        "--hidden-import", "backend.skills.web",
        "--hidden-import", "backend.skills.web.search",
        "--hidden-import", "backend.skills.web.weather",
        "--hidden-import", "backend.skills.files",
        "--hidden-import", "backend.skills.files.list",
        "--hidden-import", "backend.skills.files.read",
        "--hidden-import", "backend.skills.files.write",
        "--hidden-import", "backend.memory",
        "--hidden-import", "backend.memory.working",
        "--hidden-import", "backend.memory.short_term",
        "--hidden-import", "backend.memory.long_term",
        "--hidden-import", "backend.proactive.engine",
        "--hidden-import", "backend.evolution.engine",
        "--hidden-import", "backend.learning.compound",
        "--hidden-import", "backend.api.compat",
        "--hidden-import", "AURA_APP.desktop_ui",
        "--hidden-import", "AURA_APP.aria_logic_engine",
        "--hidden-import", "desktop_tray",
        "--hidden-import", "auto_start",
        "--hidden-import", "PyQt5",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "--collect-all", "fastapi",
        "--collect-all", "uvicorn",
        "--collect-all", "pywebview",
        "--noconfirm",
        "AURA_APP/aria_main.py",
    ]
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent.parent))
    if result.returncode == 0:
        print("[Build] Success! dist/AURA OS.exe")
    else:
        print("[Build] Failed.")
    return result.returncode


if __name__ == '__main__':
    build()
