"""
Verificador del sistema: Shadow-Core + Security Shield + Heartbeat
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "AME_Core"))

import socket
import time
from communication_bridge import get_shadow_status, is_shadow_online, start_heartbeat

# Paso 1: Verificar puerto 5001
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
result = sock.connect_ex(("127.0.0.1", 5001))
sock.close()

if result == 0:
    print("SHADOW-CORE: PUERTO 5001 LISTENING")
else:
    print("SHADOW-CORE: PUERTO 5001 OFFLINE")

# Paso 2: Iniciar heartbeat y esperar un latido
print("INICIANDO HEARTBEAT...")
start_heartbeat()
time.sleep(2)

# Paso 3: Verificar estado
status = get_shadow_status()
print(f"HEARTBEAT STATUS:  {status['status']}")
print(f"THREAT STATUS:     {status['threat_status']}")
print(f"ERROR:             {status['error']}")
print(f"SHADOW ONLINE:     {is_shadow_online()}")

# Paso 4: Verificar security_shield
from security_shield import scan_for_threats
threat = scan_for_threats()
print(f"SECURITY SHIELD:   {'ACTIVO' if threat == 'CLEAN' else 'ALERTA: ' + threat}")

# Paso 5: Verificar proxy_manager
from proxy_manager import ProxyManager
available = ProxyManager.is_shadow_core_available()
print(f"PROXY MANAGER:     {'SHADOW DISPONIBLE' if available else 'SHADOW NO DISPONIBLE'}")

# Confirmación final
if result == 0 and threat == "CLEAN":
    print("SISTEMA OPERATIVO. ESCUDO ACTIVO. HEARTBEAT IMPLEMENTADO")
else:
    print("ALERTA: Sistema con problemas detectados")