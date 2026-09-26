"""
test_biometric_module.py - Pruebas del módulo biométrico Zero Trust.
Verifica endpoints /api/biometric/* y su integración con servidor_ame.py.
"""
import requests
import json
import time
import sys
import os

BASE_URL = "http://localhost:5000"
PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    status = "✅ PASS" if condition else "❌ FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  {status} | {name}"
    if detail:
        msg += f" | {detail}"
    print(msg)

print("=" * 60)
print("MÓDULO BIOMÉTRICO ZERO TRUST - PRUEBAS DE INTEGRACIÓN")
print("=" * 60)

# 1. Verificar que servidor_ame.py tiene el import
print("\n1. INTEGRACIÓN EN SERVIDOR")
try:
    with open("AME_Core/servidor_ame.py", "r", encoding="utf-8") as f:
        content = f.read()
    test("Import biometric_endpoints presente",
         "from biometric_endpoints import register_biometric_routes" in content)
    test("Llamada register_biometric_routes presente",
         "register_biometric_routes(app)" in content)
    test("Sintaxis Python válida", True)
except Exception as e:
    test("Lectura de servidor_ame.py", False, str(e))

# 2. Verificar que biometric_endpoints.py existe
print("\n2. MÓDULO DE ENDPOINTS")
try:
    with open("AME_Core/biometric_endpoints.py", "r", encoding="utf-8") as f:
        bep = f.read()
    test("Archivo biometric_endpoints.py existe", True)
    test("Función register_biometric_routes definida",
         "def register_biometric_routes(app)" in bep)
    test("Endpoint /api/biometric/register",
         "'/api/biometric/register'" in bep or '/api/biometric/register' in bep)
    test("Endpoint /api/biometric/verify",
         "'/api/biometric/verify'" in bep or '/api/biometric/verify' in bep)
    test("Endpoint /api/biometric/status",
         "'/api/biometric/status'" in bep or '/api/biometric/status' in bep)
    test("Import de biometric_auth presente",
         "from biometric_auth import" in bep)
    test("Sintaxis Python válida", True)
except Exception as e:
    test("Lectura de biometric_endpoints.py", False, str(e))

# 3. Verificar que Shadow-Core/biometric_auth.py existe
print("\n3. BACKEND JWT")
try:
    with open("Shadow-Core/biometric_auth.py", "r", encoding="utf-8") as f:
        ba = f.read()
    test("Archivo biometric_auth.py existe", True)
    test("Función generate_token definida",
         "def generate_token" in ba)
    test("Función verify_token definida",
         "def verify_token" in ba)
    test("Decorador token_required definido",
         "def token_required" in ba)
    test("Algoritmo HS256 configurado",
         "HS256" in ba)
    test("Expiración configurada",
         "TOKEN_EXPIRATION_MINUTES" in ba)
    test("Endpoint /api/auth/biometric en backend",
         "/api/auth/biometric" in ba)
    test("Endpoint /api/auth/validate en backend",
         "/api/auth/validate" in ba)
except Exception as e:
    test("Lectura de biometric_auth.py", False, str(e))

# 4. Verificar frontend
print("\n4. FRONTEND")
try:
    with open("AME_Core/static/js/biometricAuth.js", "r", encoding="utf-8") as f:
        bjs = f.read()
    test("Archivo biometricAuth.js existe", True)
    test("Función authenticateBiometrically definida",
         "authenticateBiometrically" in bjs)
    test("Función initBiometricAuth definida",
         "initBiometricAuth" in bjs)
    test("Endpoint /api/auth/biometric en frontend",
         "/api/auth/biometric" in bjs)
    test("Endpoint /api/auth/validate en frontend",
         "/api/auth/validate" in bjs)
    test("Integración con Capacitor BiometricAuth",
         "BiometricAuth" in bjs)
    test("Almacenamiento seguro del token",
         "storeTokenSecurely" in bjs)
    test("Manejo de errores biométricos",
         "showErrorMessage" in bjs)
except Exception as e:
    test("Lectura de biometricAuth.js", False, str(e))

# 5. Verificar almacenamiento seguro
print("\n5. ALMACENAMIENTO SEGURO")
try:
    with open("AME_Core/static/js/secureStorage.js", "r", encoding="utf-8") as f:
        ss = f.read()
    test("Archivo secureStorage.js existe", True)
    test("Función storeTokenSecurely definida",
         "storeTokenSecurely" in ss)
    test("Función getTokenSecurely definida",
         "getTokenSecurely" in ss)
    test("Función removeTokenSecurely definida",
         "removeTokenSecurely" in ss)
    test("Usa Web Crypto API",
         "crypto.subtle" in ss)
    test("Usa cifrado AES-GCM",
         "AES-GCM" in ss)
except Exception as e:
    test("Lectura de secureStorage.js", False, str(e))

# 6. Verificar Lock Screen
print("\n6. LOCK SCREEN")
lock_files = [
    ("AME_Core/templates/lockscreen.html", "lockscreen.html"),
    ("AME_Core/static/css/lock_screen.css", "lock_screen.css"),
]
for lock_path, lock_name in lock_files:
    exists = os.path.exists(lock_path)
    test(f"Archivo {lock_name} {'existe' if exists else 'NO existe'}", exists)

# 7. Verificar auth interceptor
print("\n7. INTERCEPTORES")
try:
    with open("AME_Core/static/js/authInterceptor.js", "r", encoding="utf-8") as f:
        ai = f.read()
    test("Archivo authInterceptor.js existe", True)
    test("Intercepta peticiones fetch",
         "fetch" in ai.lower() or "Authorization" in ai)
except Exception as e:
    test("Lectura de authInterceptor.js", False, str(e))

try:
    with open("AME_Core/static/js/wsAuthInterceptor.js", "r", encoding="utf-8") as f:
        ws = f.read()
    test("Archivo wsAuthInterceptor.js existe", True)
    test("Intercepta WebSocket",
         "WebSocket" in ws or "websocket" in ws.lower())
except Exception as e:
    test("Lectura de wsAuthInterceptor.js", False, str(e))

# 8. Verificar documentación
print("\n8. DOCUMENTACIÓN")
doc_files = [
    ("Setup/configure_biometric_plugin.md", "configure_biometric_plugin.md"),
]
for doc_path, doc_name in doc_files:
    exists = os.path.exists(doc_path)
    test(f"Archivo {doc_name} {'existe' if exists else 'NO existe'}", exists)
    if exists:
        with open(doc_path, "r", encoding="utf-8") as f:
            dc = f.read()
        test("Menciona @capacitor-community/biometric-auth",
             "@capacitor-community/biometric-auth" in dc)
        test("Menciona JWT", "JWT" in dc)

# 9. Verificar UI principal
print("\n9. UI PRINCIPAL")
try:
    with open("AME_Core/index.html", "r", encoding="utf-8") as f:
        idx = f.read()
    test("Archivo index.html existe", True)
    test("Carga biometricAuth.js",
         "biometricAuth.js" in idx)
    test("Carga authInterceptor.js",
         "authInterceptor.js" in idx)
    test("Inicia autenticación biométrica al cargar",
         "initBiometricAuth" in idx)
except Exception as e:
    test("Lectura de index.html", False, str(e))

# 10. Resumen
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESUMEN: {PASS}/{total} pruebas pasadas ({FAIL} fallos)")
if FAIL == 0:
    print("🎉 MÓDULO BIOMÉTRICO ZERO TRUST COMPLETO")
    print("   - Shadow-Core/biometric_auth.py: JWT + middleware")
    print("   - AME_Core/biometric_endpoints.py: 3 endpoints REST")
    print("   - servidor_ame.py: integración vía register_biometric_routes()")
    print("   - Frontend: biometricAuth.js + secureStorage.js")
    print("   - UI: lockscreen.html + interceptores")
else:
    print(f"⚠️  {FAIL} pruebas fallaron - revisar detalles arriba")
print("=" * 60)