#!/usr/bin/env python3
"""ARIA OS Launcher - backend only."""
import os, sys, threading, time, urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

PORT = int(os.getenv("ARIA_PORT", os.environ.get("PORT", "8000")))

def start_backend():
    import uvicorn
    import aura_runner
    uvicorn.run(aura_runner.app, host="0.0.0.0", port=PORT, log_level="error")

t = threading.Thread(target=start_backend, daemon=True)
t.start()
print("[AURA] Backend iniciando...", flush=True)

for i in range(30):
    try:
        with urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=2) as r:
            print(f"[AURA] Backend listo: {r.read().decode()[:200]}", flush=True)
            break
    except Exception as e:
        time.sleep(0.5)
else:
    print("[AURA] ERROR: backend no respondio", flush=True)
    sys.exit(1)

print("[AURA] Backend corriendo en http://localhost:8000", flush=True)
print("[AURA] Presiona Enter para salir...", flush=True)
input()
