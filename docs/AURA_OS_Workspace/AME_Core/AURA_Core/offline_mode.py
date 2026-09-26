#!/usr/bin/env python3
"""
Offline Mode Controller para AURA.
Permite activar y desactivar el modo offline para operaciones air-gapped.
"""

import os
import subprocess
import time
import requests
import json
import sys

# Configuración global
MODEL_ROUTER_URL = "http://localhost:5011"
DNS_BLOCKER_URL = "http://localhost:5013"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def call_model_router(endpoint, data=None):
    """Llamar al Model Router."""
    try:
        url = f"{MODEL_ROUTER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Model Router ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Model Router ({endpoint}): {e}")
        return None

def call_dns_blocker(endpoint, data=None):
    """Llamar al DNS Blocker."""
    try:
        url = f"{DNS_BLOCKER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a DNS Blocker ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a DNS Blocker ({endpoint}): {e}")
        return None

def activate_offline_mode():
    """Activar el modo offline."""
    print("🔒 Activando modo offline...")

    # 1. Activar modo offline en Model Router
    model_data = {"auth_key": AUTH_KEY, "mode": True}
    model_result = call_model_router("api/models/offline", model_data)
    if not model_result or model_result.get("status") != "ok":
        print("❌ No se pudo activar modo offline en Model Router")
        return False

    # 2. Activar modo air-gapped en DNS Blocker
    dns_result = call_dns_blocker("api/airgapped/activate", {"auth_key": AUTH_KEY})
    if not dns_result or dns_result.get("status") != "ok":
        print("❌ No se pudo activar modo air-gapped en DNS Blocker")
        return False

    print("✅ Modo offline activado correctamente")
    return True

def deactivate_offline_mode():
    """Desactivar el modo offline."""
    print("🌐 Desactivando modo offline...")

    # 1. Desactivar modo offline en Model Router
    model_data = {"auth_key": AUTH_KEY, "mode": False}
    model_result = call_model_router("api/models/offline", model_data)
    if not model_result or model_result.get("status") != "ok":
        print("❌ No se pudo desactivar modo offline en Model Router")
        return False

    # 2. Desactivar modo air-gapped en DNS Blocker
    dns_result = call_dns_blocker("api/airgapped/deactivate", {"auth_key": AUTH_KEY})
    if not dns_result or dns_result.get("status") != "ok":
        print("❌ No se pudo desactivar modo air-gapped en DNS Blocker")
        return False

    print("✅ Modo offline desactivado correctamente")
    return True

def check_offline_status():
    """Verificar el estado actual del modo offline."""
    print("🔍 Verificando estado del modo offline...")

    # 1. Verificar estado en Model Router
    model_result = call_model_router("api/models/offline")
    if not model_result:
        print("❌ No se pudo verificar estado en Model Router")
        return None

    # 2. Verificar estado en DNS Blocker
    dns_result = call_dns_blocker("api/airgapped/status")
    if not dns_result:
        print("❌ No se pudo verificar estado en DNS Blocker")
        return None

    return {
        "model_router": model_result,
        "dns_blocker": dns_result
    }

def main():
    """Función principal para gestionar el modo offline."""
    print("=" * 60)
    print("🌍 Offline Mode Controller para AURA")
    print("=" * 60)

    if len(sys.argv) > 1:
        if sys.argv[1] == "--activate":
            if activate_offline_mode():
                print("\n🎉 Modo offline activado con éxito!")
                print("   - Todos los modelos están configurados para operar localmente")
                print("   - El tráfico de red está bloqueado para evitar fugas de datos")
                print("   - Solo se usan recursos locales")
            else:
                print("\n❌ No se pudo activar el modo offline")
        elif sys.argv[1] == "--deactivate":
            if deactivate_offline_mode():
                print("\n🌐 Modo offline desactivado con éxito!")
                print("   - La conectividad a internet está restaurada")
                print("   - Los modelos pueden acceder a servicios externos")
                print("   - El tráfico de red está permitido")
            else:
                print("\n❌ No se pudo desactivar el modo offline")
        elif sys.argv[1] == "--status":
            status = check_offline_status()
            if status:
                print("\n📊 Estado actual del modo offline:")
                print(f"   - Model Router: {'OFFLINE' if status['model_router'].get('offline_mode', False) else 'ONLINE'}")
                print(f"   - DNS Blocker: {'ACTIVO' if status['dns_blocker'].get('status') == 'ok' else 'INACTIVO'}")
                print(f"   - Conexión a internet: {'DISPONIBLE' if status['model_router'].get('internet_available', False) else 'NO DISPONIBLE'}")
            else:
                print("\n❌ No se pudo verificar el estado")
        else:
            print("Uso:")
            print("  python offline_mode.py --activate")
            print("  python offline_mode.py --deactivate")
            print("  python offline_mode.py --status")
    else:
        print("Uso:")
        print("  python offline_mode.py --activate    # Activar modo offline")
        print("  python offline_mode.py --deactivate  # Desactivar modo offline")
        print("  python offline_mode.py --status      # Verificar estado actual")

if __name__ == "__main__":
    main()