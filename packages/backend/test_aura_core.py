"""
Script de prueba para validar el núcleo básico de AURA OS.
Usa TestClient de FastAPI.
"""

import sys, os
sys.path.insert(0, r'C:\Users\User\Downloads\AURA')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.api.core_routes import router as core_router

app = FastAPI()
app.include_router(core_router, prefix="/api/core")

client = TestClient(app)

print("\n=== TEST 1: Health ===")
try:
    response = client.get("/health")
    print(f"GET /health → {response.status_code}")
    if response.status_code == 200:
        print("✓ PASS")
        print(f"  {response.json()}")
    else:
        print(f"  FAILED: {response.status_code}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== TEST 2: Status ===")
try:
    response = client.get("/api/core/status")
    print(f"GET /api/core/status → {response.status_code}")
    if response.status_code == 200:
        print("✓ PASS")
        result = response.json()
        print(f"  status: {result.get('status')}")
        print(f"  chunk: {result.get('chunk')}")
        print(f"  modules: {list(result.get('modules', {}).keys())}")
    else:
        print(f"  FAILED: {response.status_code}")
        print(f"  {response.text[:200]}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== TEST 3: Process ===")
try:
    payload = {
        "input": "Hola",
        "type": "chat",
        "source": "user"
    }
    response = client.post("/api/core/process", json=payload)
    print(f"POST /api/core/process → {response.status_code}")
    if response.status_code == 200:
        print("✓ PASS")
        print(f"  {response.json()}")
    else:
        print(f"  FAILED: {response.status_code}")
        print(f"  {response.text[:300]}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== FIN ===")
print("Chunk 1 verificado.")
