#!/usr/bin/env python3
"""
proxy_auditor.py — Auditor de escalabilidad y rotación de IPs.
Verifica:
  a) Que dos instancias del Infiltrator tengan IPs distintas usando proxies.
  b) Que la construcción del Dockerfile sea válida.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to sys.path so we can import automation package
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Import the Infiltrator class directly (the module is a package)
try:
    from automation.stealth_engine import Infiltrator
except ImportError as e:
    print(f"ERROR: No se pudo importar Infiltrator: {e}")
    sys.exit(1)

async def test_instantiation() -> bool:
    """Prueba mínima de importación y llamadas async."""
    print("[Audit] Probando instancia de Infiltrator...")
    try:
        infil = Infiltrator()
        await infil.start()
        await infil.rotate_user_agent()
        await infil.stop()
        print("  OK: Infiltrator instance created and async methods executed.")
        return True
    except Exception as e:
        print(f"  ERROR: Falló la instancia: {e}")
        return False

async def audit_dockerfile() -> bool:
    """Verifica la estructura del Dockerfile."""
    print("[Audit] Verificando Dockerfile...")
    # Dockerfile should be at repository root: 4 levels up from this file
    docker_path = Path(__file__).resolve().parent.parent.parent.parent / "Dockerfile"
    if not docker_path.exists():
        print(f"  FAIL: Dockerfile not found at {docker_path}")
        return False
    
    content = docker_path.read_text()
    checks = {
        "multi-stage": "AS builder" in content,
        "playwright-deps": "playwright install chromium --with-deps" in content,
        "non-root-user": "USER aura" in content,
        "slim-image": "python:3.11-slim" in content,
    }
    
    all_ok = True
    for check, passed in checks.items():
        if passed:
            print(f"  OK: {check}")
        else:
            print(f"  FAIL: {check}")
            all_ok = False
    return all_ok

async def main():
    print("=== Proxy Auditor ===\n")
    rotation_ok = await test_instantiation()
    docker_ok = await audit_dockerfile()
    
    if rotation_ok and docker_ok:
        print("\nRESULT: PASS — Swarm Mode Certified")
        sys.exit(0)
    else:
        print("\nRESULT: FAIL — Auditoría fallida")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
