#!/usr/bin/env python3
# BLOQUE 104 - Verificacion de humo E2E del runtime maestro (TestClient).
# 100% local, offline. No requiere uvicorn real.
from __future__ import annotations
import sys
from fastapi.testclient import TestClient
from backend.main import app

ENDPOINTS = [
    ('GET', '/api/aura/master/status', {}, 'master_status'),
    ('GET', '/api/aura/master/launch', {}, 'master_launch'),
    ('GET', '/health', {}, 'health'),
    ('GET', '/api/core/sovereign-lock/status', {}, 'lock_status'),
    ('GET', '/api/core/sovereign-lock/contracts', {}, 'lock_contracts'),
    ('GET', '/api/core/sovereign-lock/smoke', {}, 'lock_smoke'),
    ('GET', '/api/testing/matrix/status', {}, 'matrix_status'),
    ('GET', '/api/testing/matrix/contracts', {}, 'matrix_contracts'),
]

def run(url, method='GET', body=None):
    f = getattr(c, method.lower())
    r = f(url, json=body) if body is not None else f(url)
    return (r.status_code == 200, r.json() if r.status_code == 200 else None,
            getattr(r, 'text', ''))

if __name__ == '__main__':
    c = TestClient(app)
    steps = 0
    ok = 0
    for method, path, body, label in ENDPOINTS:
        try:
            status, payload, _ = run(path, method, body)
            steps += 1
            if status:
                ok += 1
            print(f'[{"OK" if status else "FAIL"}] {label} {method} {path}')
            if payload and ('sovereign_ready' in payload or 'offline_only' in payload):
                print(f'    sovereign_ready={payload.get("sovereign_ready")} offline_only={payload.get("offline_only")}')
            if payload and 'block' in payload:
                print(f'    block={payload.get("block")}')
            if payload and 'status' in payload and 'block' not in payload:
                print(f'    status={payload.get("status")}')
        except Exception as exc:
            steps += 1
            print(f'[FAIL] {label} -> {exc}')

    master_ok, _ = run('/api/aura/master/status')
    print()
    if master_ok:
        print('PASS: API Gateway responde -> 200 OK')
    else:
        print('FAIL: API Gateway no responde')
    print()
    if ok == steps and master_ok:
        print('VEREDICTO: AURA SOVEREIGN READY')
    else:
        print(f'VEREDICTO: AURA parcial -> {ok}/{steps} checks OK')
