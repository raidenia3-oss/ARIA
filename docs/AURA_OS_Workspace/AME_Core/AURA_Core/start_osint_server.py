"""
Script para iniciar el servidor OSINT de AURA.
Este servidor proporciona endpoints seguros para realizar búsquedas OSINT.
"""

import os
import sys
import subprocess
from api_routes import app

def start_osint_server():
    """
    Inicia el servidor OSINT de AURA en un puerto específico.
    """
    print("🚀 Iniciando servidor OSINT de AURA...")
    print("🔒 Endpoint protegido: /api/search (requiere X-API-KEY)")
    print("📡 Endpoint de salud: /api/health")

    # Configuración del puerto (puede ser configurado en un archivo de configuración)
    port = 5000

    # Verificar si el puerto está disponible
    try:
        # Intentar iniciar el servidor
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        print(f"⚠️ Error al iniciar el servidor: {e}")
        print("🔍 Verificando si otro proceso está usando el puerto...")
        try:
            # Intentar matar procesos que puedan estar usando el puerto
            subprocess.run(["lsof", "-i", f":{port}"], check=True)
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            print("⚠️ Comando 'lsof' no disponible. Intenta manualmente liberar el puerto.")

        print(f"🔄 Reiniciando servidor en el puerto {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    start_osint_server()