#!/usr/bin/env python3
"""ARIA OS Launcher - backend + webview."""
import os, sys, threading, time, urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

PORT = int(os.getenv("ARIA_PORT", os.environ.get("PORT", "8000")))

def start_backend():
    import uvicorn
    import aura_runner
    uvicorn.run(aura_runner.app, host="0.0.0.0", port=PORT, log_level="error")

def wait_backend(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    t = threading.Thread(target=start_backend, daemon=True)
    t.start()
    print("[AURA] Backend iniciando...", flush=True)
    ready = wait_backend()
    if not ready:
        print("WARNING: backend no respondio", flush=True)

    import webview
    window = webview.create_window(
        title="ARIA OS v2.0",
        url="http://localhost:8000",
        width=1280, height=800,
        resizable=True, fullscreen=False,
        frameless=False, easy_drag=True,
        background_color="#050816",
    )
    webview.start(debug=False, gui="edgechromium")

if __name__ == "__main__":
    main()
