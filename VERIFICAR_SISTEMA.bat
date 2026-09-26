@echo off
chcp 65001 >nul
title AURA - Verificacion del Sistema
echo.
echo ==========================================
echo   AURA - Verificacion Completa del Sistema
echo ==========================================
echo.

set "PYTHON=python"
set "BACKEND_URL=http://localhost:8000"
set "API_KEY=test-key"

echo [1/4] Verificando backend local...
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado
    pause
    exit /b 1
)

echo.
echo [2/4] Iniciando backend...
start "AURA Backend" /B python -m backend.main

echo Esperando que el backend inicie...
timeout /t 5 /nobreak >nul

echo.
echo [3/4] Ejecutando pruebas automatizadas...
echo.

python -c "
import urllib.request
import json
import sys

BASE = '%BACKEND_URL%'
HEADERS = {'Content-Type': 'application/json', 'X-API-Key': '%API_KEY%'}
PASS = 0
FAIL = 0

def test(name, method, path, body=None, headers=None):
    global PASS, FAIL
    url = BASE + path
    h = HEADERS.copy()
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            resp = json.loads(r.read())
            ok = status == 200
            if ok:
                PASS += 1
                print(f'  [OK] {name}')
            else:
                FAIL += 1
                print(f'  [FAIL] {name} -> status={status}')
    except Exception as e:
        FAIL += 1
        print(f'  [FAIL] {name} -> {e}')

print('=== JARVIS Core ===')
test('Health', 'GET', '/health')
test('Chat', 'POST', '/api/chat', {'prompt': 'hola', 'session_id': 'verify'})
test('TTS', 'POST', '/api/tts', {'text': 'test', 'voice': 'default'})
test('Device Automate', 'POST', '/api/device/automate', {'action': 'open_url', 'params': {'url': 'https://godotengine.org'}})
test('Agent Command', 'POST', '/api/agent/command', {'command': 'status', 'device': 'local'})

print('')
print('=== Vision HUD ===')
test('Gesture Predict', 'POST', '/api/gesture/predict', {'image_base64': ''})
test('Gesture Stream', 'GET', '/api/gesture/stream')

print('')
print('=== Pentesting and Telemetry ===')
test('WiFi Scan', 'POST', '/api/wifi/scan', {})
test('Network Topology', 'POST', '/api/network/topology', {})
test('System Telemetry', 'GET', '/api/system/telemetry')

print('')
print('=== Brain and Orchestrator ===')
test('Brain Status', 'GET', '/api/brain')
test('Orchestrator', 'GET', '/api/orchestrator')

print('')
print('==========================================')
print(f'  Resultado: {PASS} OK, {FAIL} FAIL')
print('==========================================')
if FAIL == 0:
    print('  TODO FUNCIONANDO CORRECTAMENTE')
else:
    print('  Hay modulos con errores - revisar logs')
print('')
input('Presiona Enter para cerrar...')
"

echo.
echo [4/4] Limpiando...
taskkill /FI "WINDOWTITLE eq AURA Backend*" /F >nul 2>&1

echo.
echo ==========================================
echo   Verificacion completada
echo ==========================================
pause
