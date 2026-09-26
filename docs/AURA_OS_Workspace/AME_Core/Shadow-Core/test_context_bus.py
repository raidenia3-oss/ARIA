#!/usr/bin/env python3
"""
Script de prueba para el Shared Context Bus.
Demuestra cómo los agentes pueden compartir contexto entre sí.
"""

import requests
import time
import json
from datetime import datetime

# Configuración global
MODEL_ROUTER_URL = "http://localhost:5011"
LLM_ANALYZER_URL = "http://localhost:5014"
CONTEXT_BUS_URL = "http://localhost:5015"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def call_model_router(endpoint, data=None):
    """Llamar al Model Router."""
    try:
        url = f"{MODEL_ROUTER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Model Router ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Model Router ({endpoint}): {e}")
        return None

def call_llm_analyzer(endpoint, data=None):
    """Llamar al LLM Analyzer."""
    try:
        url = f"{LLM_ANALYZER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a LLM Analyzer ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a LLM Analyzer ({endpoint}): {e}")
        return None

def call_context_bus(endpoint, data=None):
    """Llamar al Shared Context Bus."""
    try:
        url = f"{CONTEXT_BUS_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Context Bus ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Context Bus ({endpoint}): {e}")
        return None

def publish_research_result():
    """Publicar un resultado de investigación en el Context Bus."""
    print("\n🔍 Publicando resultado de investigación en el Context Bus...")

    research_result = {
        "agent_type": "research_agent",
        "type": "research_results",
        "summary": "Investigación sobre optimización de servidores: mejores prácticas y herramientas",
        "content": """
        # Investigación sobre Optimización de Servidores

        ## 1. Actualización de Software
        - Mantener actualizado el sistema operativo, controladores y aplicaciones.
        - Usar versiones estables y probadas de todo el software.
        - Implementar un sistema de parches automáticos para actualizaciones de seguridad.

        ## 2. Optimización de la Base de Datos
        - Implementar índices adecuados para las consultas más frecuentes.
        - Realizar análisis regulares de consultas lentas y optimizar las más críticas.
        - Considerar la partición de tablas grandes para mejorar el rendimiento.

        ## 3. Caching
        - Implementar un sistema de caché como Redis para almacenar resultados de consultas frecuentes.
        - Configurar TTL (Time To Live) adecuados para los datos en caché.
        - Usar caché en múltiples capas (aplicación, base de datos, CDN).

        ## 4. Hardware
        - Asegurarse de que el servidor tenga suficiente RAM, CPU y almacenamiento.
        - Considerar la actualización a hardware más potente si el servidor está sobrecargado.
        - Usar discos SSD en lugar de HDD para mejorar el rendimiento de E/S.

        ## 5. Configuración del Servidor
        - Optimizar la configuración del sistema operativo (ej: parámetros de kernel en Linux).
        - Ajustar los límites de recursos según la carga del servidor.
        - Usar herramientas como `sysctl` en Linux para optimizar el rendimiento.

        ## 6. Monitoreo y Análisis
        - Implementar herramientas de monitoreo como Prometheus y Grafana para visualizar métricas en tiempo real.
        - Usar herramientas como `top`, `htop`, `vmstat` y `iostat` para analizar el uso de recursos.
        - Configurar alertas para notificarte cuando los recursos estén cerca de su límite.

        ## 7. Balanceo de Carga
        - Implementar balanceo de carga si el servidor maneja múltiples servicios o alta demanda.
        - Usar herramientas como Nginx, HAProxy o AWS ALB para distribuir la carga.

        ## 8. Optimización de Aplicaciones
        - Revisar el código de las aplicaciones para identificar cuellos de botella.
        - Implementar técnicas de optimización como lazy loading, paginación y compresión.
        - Usar frameworks y librerías optimizadas para las tareas específicas.

        ## 9. Red y Redes
        - Optimizar la configuración de red (ej: MTU, buffer sizes).
        - Usar conexiones persistentes para bases de datos y servicios externos.
        - Considerar la implementación de CDN para contenido estático.

        ## 10. Seguridad y Estabilidad
        - Implementar medidas de seguridad adecuadas para evitar ataques que puedan degradar el rendimiento.
        - Realizar pruebas de carga para identificar puntos débiles antes de que afecten a los usuarios.
        - Implementar estrategias de recuperación ante fallos (ej: réplicas, backups).

        ## Herramientas Recomendadas
        - **Monitoreo**: Prometheus, Grafana, Datadog, New Relic
        - **Base de Datos**: MySQLTuner, pgTuner, MongoDB Atlas
        - **Caching**: Redis, Memcached
        - **Balanceo de Carga**: Nginx, HAProxy, AWS ALB, Cloudflare
        - **Pruebas de Carga**: JMeter, Locust, k6, Apache Benchmark
        """,
        "format": "markdown"
    }

    result = call_context_bus("api/context_bus/publish", {
        "auth_key": AUTH_KEY,
        "context": research_result
    })

    if result and result.get("status") == "ok":
        print(f"✅ Resultado de investigación publicado con ID: {result.get('context_id')}")
        return result.get("context_id")
    else:
        print("❌ Error al publicar resultado de investigación")
        return None

def get_research_context():
    """Obtener contexto de investigación del Context Bus."""
    print("\n🔍 Obteniendo contexto de investigación del Context Bus...")

    result = call_context_bus("api/context_bus/get/type/RESEARCH_TASK", {"limit": 5})
    if result and result.get("status") == "ok":
        print(f"✅ Encontrados {len(result.get('contexts', []))} elementos de contexto de investigación:")
        for context in result.get("contexts", []):
            print(f"   - {context.get('summary', 'Sin resumen')} (ID: {context.get('context_id')})")
        return result.get("contexts", [])
    else:
        print("❌ Error al obtener contexto de investigación")
        return []

def implement_code_based_on_research():
    """Implementar código basado en el contexto de investigación obtenido."""
    print("\n💻 Implementando código basado en el contexto de investigación...")

    # Obtener contexto de investigación
    research_context = get_research_context()
    if not research_context:
        print("⚠️ No hay contexto de investigación disponible. Usando un ejemplo genérico.")
        research_context = [{
            "summary": "Investigación sobre optimización de servidores",
            "content": "Optimizar servidores implica actualizar software, configurar bases de datos, implementar caching, y usar herramientas de monitoreo como Prometheus y Grafana."
        }]

    # Seleccionar un elemento de contexto para usar como referencia
    context_item = research_context[0] if research_context else None

    # Crear un prompt basado en el contexto de investigación
    prompt = f"""
    Basado en la siguiente investigación sobre optimización de servidores:

    {context_item.get('content', 'Investigación sobre optimización de servidores')}

    Por favor, implementa un script en Python que:
    1. Monitoree el uso de CPU, memoria y disco en tiempo real.
    2. Genere alertas si algún recurso supera el 80% de su capacidad.
    3. Guarde los datos en un archivo CSV para análisis posterior.
    4. Incluya un dashboard simple usando matplotlib para visualizar las métricas.

    Usa las mejores prácticas mencionadas en la investigación, como Prometheus para monitoreo y Redis para caching si es necesario.
    """

    system_prompt = """
    Eres un experto en programación y optimización de servidores.
    Proporciona un script Python completo, bien estructurado y comentado.
    Usa librerías estándar como psutil para monitoreo y pandas/matplotlib para análisis y visualización.
    Asegúrate de que el script sea funcional y pueda ejecutarse en un entorno típico de servidor.
    """

    # Analizar con el LLM Analyzer (que usará el Model Router)
    result = call_llm_analyzer("api/llm/analyze", {
        "auth_key": AUTH_KEY,
        "prompt": prompt,
        "system_prompt": system_prompt
    })

    if result and result.get("status") == "ok":
        print("✅ Código implementado basado en el contexto de investigación:")
        print("=" * 80)
        print(result.get("response"))
        print("=" * 80)

        # Publicar el código generado en el Context Bus
        code_context = {
            "agent_type": "code_agent",
            "type": "implementations",
            "summary": "Implementación de script de monitoreo de servidores basado en investigación previa",
            "content": result.get("response"),
            "format": "python",
            "related_context": context_item.get("context_id") if context_item else None
        }

        code_result = call_context_bus("api/context_bus/publish", {
            "auth_key": AUTH_KEY,
            "context": code_context
        })

        if code_result and code_result.get("status") == "ok":
            print(f"\n✅ Código publicado en el Context Bus con ID: {code_result.get('context_id')}")
        else:
            print(f"\n⚠️ No se pudo publicar el código en el Context Bus")

        return result.get("response")
    else:
        print("❌ Error al implementar código basado en el contexto de investigación")
        return None

def get_global_knowledge():
    """Obtener el conocimiento global acumulado."""
    print("\n📚 Obteniendo conocimiento global acumulado...")

    result = call_context_bus("api/context_bus/global_knowledge")
    if result and result.get("status") == "ok":
        print(f"✅ Conocimiento global obtenido (tamaño: {len(result.get('content', ''))} caracteres)")
        print(f"Última actualización: {result.get('last_modified')}")
        return result.get("content", "")
    else:
        print("❌ Error al obtener conocimiento global")
        return ""

def main():
    """Función principal para demostrar el intercambio de contexto entre agentes."""
    print("=" * 80)
    print("🔄 DEMOSTRACIÓN DEL SHARED CONTEXT BUS")
    print("=" * 80)
    print("Este script demuestra cómo los agentes de AURA pueden compartir contexto:")
    print("1. El Research Agent publica resultados de investigación en el Context Bus.")
    print("2. El Code Agent recupera ese contexto y lo usa para implementar código.")
    print("3. Ambos agentes contribuyen al conocimiento global del sistema.")
    print("=" * 80)

    # Paso 1: Publicar un resultado de investigación
    research_id = publish_research_result()
    time.sleep(2)  # Esperar a que el contexto se propague

    # Paso 2: Implementar código basado en el contexto de investigación
    code_result = implement_code_based_on_research()
    time.sleep(2)  # Esperar a que el código se procese

    # Paso 3: Verificar el conocimiento global acumulado
    global_knowledge = get_global_knowledge()
    print("\n📝 Primeras 500 líneas del conocimiento global:")
    print("-" * 80)
    print(global_knowledge[:500] + "..." if len(global_knowledge) > 500 else global_knowledge)
    print("-" * 80)

    print("\n🎉 Demostración completada con éxito!")
    print("\nResumen del flujo:")
    print("1. Research Agent → Publica investigación en Context Bus")
    print("2. Context Bus → Comparte investigación con otros agentes")
    print("3. Code Agent → Recupera investigación y genera código")
    print("4. Code Agent → Publica implementación en Context Bus")
    print("5. Conocimiento global → Se actualiza automáticamente")

if __name__ == "__main__":
    main()