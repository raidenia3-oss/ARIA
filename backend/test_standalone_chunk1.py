"""Prueba del Chunk 1 usando httpx."""
import sys, os, time, subprocess, sys

sys.path.insert(0, r'C:\Users\User\Downloads\AURA')

import httpx
import subprocess
from concurrent.futures import ThreadPoolExecutor
import time

BASE = "http://localhost:8000"

def wait_for_server(timeout=20):
    for _ in range(timeout):
        try:
            r = httpx.get(f"{BASE}/health", timeout=0.5)
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False

def run_tests():
    with httpx.Client() as client:
        # 1. Health
        print("\n1. GET /health")
        r = client.get(f"{BASE}/health")
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(json.dumps(r.json(), indent=2))

        # 2. Status
        print("\n2. GET /api/core/status")
        r = client.get(f"{BASE}/api/core/status")
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(json.dumps(r.json(), indent=2))

        # 3. Process
        print("\n3. POST /api/core/process")
        payload = {"input": "Hola", "type": "chat", "source": "user"}
        r = client.post(f"{BASE}/api/core/process", json=payload)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(json.dumps(r.json(), indent=2))

        # 4. Generate code
        print("\n4. GET /api/core/generate-code")
        params = {"description": "modulo de notificaciones", "language": "python"}
        r = client.get(f"{BASE}/api/core/generate-code", params=params)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(json.dumps(r.json(), indent=2))

        # 5. Reset
        print("\n5. POST /api/core/reset")
        r = client.post(f"{BASE}/api/core/reset")
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(json.dumps(r.json(), indent=2))

    print("\n=== FIN ===")

if __name__ == '__main__':
    from multiprocessing import Process
    import sys
    import subprocess
    import sys
    import sys

    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main_chunk1:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=r"C:\Users\User\Downloads\AURA\backend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    print("Esperando servidor...")
    if wait_for_server(10):
        print("Servidor listo")
        run_tests()
    else:
        print("Time out")
        server_process.terminate()
        sys.exit(1)

    server_process.terminate()
    server_process.wait()
