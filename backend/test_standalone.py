"""
Prueba del servidor AURA OS usando httpx.
"""
import sys, os, time, subprocess, signal

sys.path.insert(0, r'C:\Users\User\Downloads\AURA')

import httpx

# Definitions
BASE_URL = "http://localhost:8000"
HEALTH = f"{BASE_URL}/health"
STATUS = f"{BASE_URL}/api/core/status"
PROCESS = f"{BASE_URL}/api/core/process"
GEN_CODE = f"{BASE_URL}/api/core/generate-code"
RESET = f"{BASE_URL}/api/core/reset"

def main():
    # Start uvicorn in background
    log_file = open(os.path.join(os.path.dirname(__file__), "server.log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
        cwd=r"C:\Users\User\Downloads\AURA\backend",
        stdout=log_file,
        stderr=subprocess.STDOUT
    )

    # Wait for server to be ready
    print("Esperando servidor...")
    for _ in range(30):
        try:
            with httpx.Client() as client:
                r = client.get(HEALTH, timeout=1.0)
                if r.status_code == 200:
                    print("Servidor listo")
                    break
        except Exception as e:
            pass
        time.sleep(1)
    else:
        print("Time out esperando servidor")
        proc.terminate()
        return

    with httpx.Client() as client:
        # 1. Health check
        print("\n1. GET /health")
        r = client.get(HEALTH)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(f"   Respuesta: {r.json()}")
        else:
            print("   FAIL")

        # 2. Status
        print("\n2. GET /api/core/status")
        r = client.get(STATUS)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(f"   Respuesta: {r.json()}")
        else:
            print("   FAIL")
            print(f"   {r.text[:300]}")

        # 3. Process
        print("\n3. POST /api/core/process")
        payload = {"input": "Hola", "type": "chat", "source": "user"}
        r = client.post(PROCESS, json=payload)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(f"   Respuesta: {r.json()}")
        else:
            print("   FAIL")
            print(f"   {r.text[:300]}")

        # 4. Generate code
        print("\n4. GET /api/core/generate-code")
        params = {"description": "modulo de notificaciones", "language": "python"}
        r = client.get(GEN_CODE, params=params)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(f"   Respuesta: {r.json()}")
        else:
            print("   FAIL")
            print(f"   {r.text[:300]}")

        # 5. Reset
        print("\n5. POST /api/core/reset")
        r = client.post(RESET)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print("   PASS")
            print(f"   Respuesta: {r.json()}")
        else:
            print("   FAIL")
            print(f"   {r.text[:300]}")

    # Stop server
    proc.terminate()
    proc.wait(timeout=5)
    log_file.close()
    print("\n=== FIN ===")

if __name__ == "__main__":
    main()
