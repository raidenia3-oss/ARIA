"""
test_llm_integration.py - Script para probar la integración completa del LLM en el sistema AURA
Este script simula el flujo completo desde el feed RSS hasta la ejecución de acciones.
"""

import requests
import json
import time
import threading
import subprocess
import os
import sys
import signal
from datetime import datetime

# Configuración de puertos
DATA_FEED_PORT = 5002
DECISION_CORE_PORT = 5001
ACTION_EXECUTOR_PORT = 5003

# Función para iniciar servidores en procesos separados
def start_server(server_name, command, port):
    """Inicia un servidor en un proceso separado"""
    def target():
        try:
            print(f"Iniciando {server_name} en el puerto {port}...")
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return process
        except Exception as e:
            print(f"Error al iniciar {server_name}: {str(e)}")
            return None

    return target()

# Función para probar el LLM Analyzer directamente
def test_llm_analyzer_directly():
    """Prueba el módulo LLM Analyzer directamente"""
    print("\n=== PRUEBA DIRECTA DEL LLM ANALYZER ===")

    try:
        # Importar el módulo correctamente
        sys.path.append(os.path.join(os.path.dirname(__file__), "Shadow-Core"))
        from llm_analyzer import process_news_article

        test_news = {
            "title": "Critical Vulnerability in Popular CMS Exploited in the Wild",
            "description": """
            Security researchers have discovered a critical vulnerability (CVE-2023-1234) in a widely used
            Content Management System (CMS) that is currently being exploited in targeted attacks.
            The vulnerability allows remote code execution and affects versions 3.2.1 through 4.1.2.
            Multiple advanced persistent threat (APT) groups have been observed using this vulnerability
            to gain initial access to corporate networks. The vulnerability was disclosed by a security
            firm after being actively exploited for over two weeks. Patches are available but many
            organizations remain unpatched due to the complexity of the update process.
            """,
            "url": "https://example.com/security/alert/critical-cms-vulnerability",
            "date": "2023-11-15T14:30:00Z"
        }

        analysis = process_news_article(test_news)
        print("Análisis generado por el LLM Analyzer:")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        return True

    except Exception as e:
        print(f"Error al probar el LLM Analyzer: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# Función para probar la integración completa
def test_llm_integration():
    """
    Prueba la integración completa del LLM en el sistema AURA
    """
    try:
        # Iniciar servidores
        print("Iniciando servidores para la prueba de integración...")

        # Iniciar Action Executor
        action_executor = start_server("Action Executor", f"python Shadow-Core/action_executor.py", ACTION_EXECUTOR_PORT)
        time.sleep(2)

        # Iniciar Decision Core
        decision_core = start_server("Decision Core", f"python AURA_Core/decision_core.py", DECISION_CORE_PORT)
        time.sleep(2)

        # Iniciar Data Feed (Shadow-Core)
        data_feed = start_server("Data Feed", f"python Shadow-Core/data_feed.py", DATA_FEED_PORT)
        time.sleep(5)  # Esperar a que todos los servidores inicien

        # Simular una alerta manual usando el Decision Core
        print("\nSimulando alerta manual con análisis del LLM...")

        test_alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "osint_news",
            "id": "test_llm_integration_1",
            "type": "security_news",
            "severity": "medium",
            "title": "Critical Vulnerability in Popular CMS Exploited in the Wild",
            "description": """
            Security researchers have discovered a critical vulnerability (CVE-2023-1234) in a widely used
            Content Management System (CMS) that is currently being exploited in targeted attacks.
            The vulnerability allows remote code execution and affects versions 3.2.1 through 4.1.2.
            Multiple advanced persistent threat (APT) groups have been observed using this vulnerability
            to gain initial access to corporate networks. The vulnerability was disclosed by a security
            firm after being actively exploited for over two weeks. Patches are available but many
            organizations remain unpatched due to the complexity of the update process.
            """,
            "details": [
                {"type": "url", "value": "https://example.com/security/alert/critical-cms-vulnerability"},
                {"type": "source", "value": "The Hacker News"},
                {"type": "published", "value": "2023-11-15T14:30:00Z"}
            ],
            "metadata": {
                "url": "https://example.com/security/alert/critical-cms-vulnerability",
                "source": "The Hacker News",
                "confidence": 0.95,
                "last_seen": datetime.utcnow().isoformat(),
                "published": "2023-11-15T14:30:00Z"
            }
        }

        # Enviar la alerta al Decision Core
        print("Enviando alerta al Decision Core...")
        response = requests.post(
            f"http://localhost:{DECISION_CORE_PORT}/api/simulate",
            json=test_alert
        )

        if response.status_code == 200:
            result = response.json()
            print(f"Respuesta del Decision Core: {result['status']}")

            if result['status'] == 'success':
                processed_alert = result['alert']

                print("\n=== ALERTA PROCESADA ===")
                print(f"Título: {processed_alert.get('original_alert', {}).get('title', 'Desconocido')}")
                print(f"Severidad: {processed_alert.get('severity', 'Desconocido')}")
                print(f"Nivel de amenaza (LLM): {processed_alert.get('threat_level', 'Desconocido')}")
                print(f"Resumen táctico: {processed_alert.get('resumen_tactico', 'Desconocido')}")

                print("\n=== ACCIONES RECOMENDADAS ===")
                for i, action in enumerate(processed_alert.get('recommended_actions', []), 1):
                    print(f"{i}. {action.get('description', 'Desconocido')} (Prioridad: {action.get('priority', 'medium')})")

                print("\n=== TAGS ===")
                print(", ".join(processed_alert.get('tags', [])))

                # Verificar si se generó una acción en la cola
                if processed_alert.get('action_required', False):
                    print("\n=== ACCIÓN EN COLA ===")
                    print("La alerta requiere acción y ha sido añadida a la cola de acciones pendientes.")

                    # Esperar un momento para que la acción se procese
                    time.sleep(3)

                    # Verificar el estado del Decision Core
                    status_response = requests.get(f"http://localhost:{DECISION_CORE_PORT}/api/status")
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"\nEstado del Decision Core:")
                        print(f"- Acciones pendientes: {status.get('pending_actions', 0)}")
                        print(f"- Acciones aprobadas: {status.get('approved_actions', 0)}")
                        print(f"- Acciones completadas: {status.get('completed_actions', 0)}")

                        if status.get('pending_actions', 0) > 0:
                            print("\n¡Éxito! La integración del LLM está funcionando correctamente.")
                            print("El sistema ha procesado la alerta con el LLM, generado un resumen táctico,")
                            print("determinado el nivel de amenaza y creado acciones recomendadas.")
                            print("La alerta ha sido añadida correctamente a la cola de acciones pendientes.")
                        else:
                            print("\nAdvertencia: No se encontraron acciones pendientes en la cola.")
                            print("Posible problema en la comunicación entre componentes.")

                else:
                    print("\nAdvertencia: La alerta no requiere acción.")
            else:
                print(f"Error al procesar la alerta: {result.get('message', 'Desconocido')}")
        else:
            print(f"Error al enviar alerta al Decision Core. Código de estado: {response.status_code}")
            print(f"Respuesta: {response.text}")

    except Exception as e:
        print(f"Error al probar la integración del LLM: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Detener servidores
        print("\nDeteniendo servidores...")
        os.system("taskkill /F /IM python.exe /T")

if __name__ == "__main__":
    print("Iniciando prueba de integración del LLM en AURA...")

    # Primero probar el LLM Analyzer directamente
    llm_success = test_llm_analyzer_directly()

    if llm_success:
        print("\nEl LLM Analyzer está funcionando correctamente.")
        print("Procediendo con la prueba de integración completa...")

        # Probar la integración completa
        test_llm_integration()
    else:
        print("\nEl LLM Analyzer no está funcionando correctamente.")
        print("No se puede continuar con la prueba de integración.")