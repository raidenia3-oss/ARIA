"""ARIA Native Launcher — desktop window via pywebview, inspired by deepakrakshit/jarvis and JEGAN-tom/Tom-s-Assistant."""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
FRONTEND_INDEX = APP_DIR / "frontend" / "index.html"
BACKEND_SCRIPT = APP_DIR / "run_app.py"


def start_backend() -> None:
    import subprocess
    python = sys.executable
    backend_script = os.path.join(str(APP_DIR), "run_app.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(APP_DIR) + os.pathsep + str(APP_DIR.parent)
    subprocess.Popen(
        [python, backend_script],
        cwd=str(APP_DIR.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def wait_backend_ready(timeout: int = 20) -> bool:
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main() -> int:
    if not FRONTEND_INDEX.exists():
        print(f"ERROR: frontend not found at {FRONTEND_INDEX}")
        return 1

    t = threading.Thread(target=start_backend, daemon=True)
    t.start()
    print("Starting AURA backend...")

    ready = wait_backend_ready(timeout=25)
    if not ready:
        print("WARNING: backend did not respond in time, opening UI anyway")

    import webview
    window = webview.create_window(
        title="ARIA OS v2.0",
        url=f"file:///{FRONTEND_INDEX.as_posix()}",
        width=1280,
        height=800,
        resizable=True,
        fullscreen=False,
        frameless=False,
        easy_drag=True,
        background_color="#050816",
    )
    webview.start(debug=False, http_server=False, gui="edgechromium")
    return 0


if __name__ == "__main__":
    sys.exit(main())
