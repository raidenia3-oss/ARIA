"""
Script para integrar el Shadow-Core en el servidor AME.
"""

import sys
import os
import subprocess
import time
import threading

# Añadir AME_Core al path para importar módulos
AME_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if AME_CORE_DIR not in sys.path:
    sys.path.insert(0, AME_CORE_DIR)

# Importar módulos del Shadow-Core
from proxy_manager import ProxyManager
from security_shield import scan_for_threats

def start_shadow_core_process():
    """
    Inicia el proceso del Shadow-Core en segundo plano.
    Verifica amenazas antes de iniciar el proceso.
    """
    try:
        # Verificar amenazas antes de iniciar el Shadow-Core
        threat_status = scan_for_threats()
        if threat_status != "CLEAN":
            print(f"❌ No se puede iniciar el Shadow-Core: {threat_status}")
            return None

        # Ruta al script del Shadow-Core
        shadow_core_path = os.path.join(AME_CORE_DIR, "shadow_core.py")

        # Iniciar el proceso del Shadow-Core
        process = subprocess.Popen(
            [sys.executable, shadow_core_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )

        # Esperar un momento para que el servidor inicie
        time.sleep(2)

        # Verificar si el Shadow-Core está disponible
        if ProxyManager.is_shadow_core_available():
            print("✅ Shadow-Core iniciado correctamente en el puerto 5001.")
            print("🛡️ Seguridad verificada: Entorno libre de amenazas.")
            return process
        else:
            print("❌ No se pudo conectar al Shadow-Core. Verifica que el puerto 5001 esté disponible.")
            return None

    except Exception as e:
        print(f"❌ Error iniciando el Shadow-Core: {e}")
        return None

def integrate_shadow_core(app, logger):
    """
    Integra el Shadow-Core en la aplicación Flask.
    :param app: Instancia de la aplicación Flask.
    :param logger: Logger de Flask para registrar eventos.
    """
    # Iniciar el proceso del Shadow-Core en segundo plano
    shadow_core_process = start_shadow_core_process()

    if shadow_core_process:
        # Registrar el endpoint para ejecutar comandos avanzados
        @app.route('/api/osint/execute', methods=['POST'])
        def api_osint_execute():
            """
            Endpoint para ejecutar comandos avanzados de OSINT a través del Shadow-Core.
            """
            try:
                from flask import request

                # Obtener el cuerpo de la petición
                body = request.json

                # Validar que sea un JSON válido
                if not isinstance(body, dict):
                    return {"status": "failed", "message": "El cuerpo de la petición debe ser un JSON válido."}, 400

                # Ejecutar el comando a través del Proxy Manager
                result = ProxyManager.execute_advanced_command(body)

                # Retornar el resultado
                return result, 200 if result.get("status") == "ok" else 500

            except Exception as e:
                logger.error(f"❌ Error ejecutando comando OSINT: {e}")
                return {"status": "failed", "message": f"Error interno: {str(e)}"}, 500

        # Mensaje de confirmación
        logger.info("✅ Shadow-Core integrado correctamente")
        logger.info("🔄 Endpoint disponible: /api/osint/execute")
        logger.info("🛡️ Proxy Manager activado como Circuit Breaker")

        # Retornar el proceso del Shadow-Core para gestionarlo más tarde
        return shadow_core_process
    else:
        logger.error("❌ No se pudo integrar el Shadow-Core")
        return None