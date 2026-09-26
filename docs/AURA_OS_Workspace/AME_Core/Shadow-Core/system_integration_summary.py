"""
system_integration_summary.py - Resumen de la integración del sistema de datos en tiempo real
Este script genera un informe completo del estado actual de la integración
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del sistema
SYSTEM_CONFIG = {
    "shadow_core_path": Path("Shadow-Core"),
    "data_feed_path": "data_feed.py",
    "start_script_path": "start_data_feed.py",
    "frontend_integration_path": Path("AME_Core/integrate_data_feed.py"),
    "frontend_js_path": Path("AME_Core/static/js/data_feed_integration.js"),
    "dashboard_path": Path("AME_Core/templates/osint_dashboard.html"),
    "test_files": [
        {"path": "Shadow-Core/data_feed.py", "name": "data_feed.py"},
        {"path": "Shadow-Core/start_data_feed.py", "name": "start_data_feed.py"},
        {"path": "AME_Core/integrate_data_feed.py", "name": "integrate_data_feed.py"},
        {"path": "AME_Core/static/js/data_feed_integration.js", "name": "data_feed_integration.js"},
        {"path": "AME_Core/templates/osint_dashboard.html", "name": "osint_dashboard.html"},
        {"path": "ui_engine/knowledge_nodes.js", "name": "knowledge_nodes.js"}
    ],
    "required_dependencies": [
        "flask",
        "flask-socketio",
        "eventlet",
        "python-dotenv"
    ],
    "test_ports": [5002, 5003]
}

# Variables globales para el estado del sistema
system_status = {
    "files_exist": False,
    "code_structure_ok": False,
    "dashboard_ok": False,
    "knowledge_integration_ok": False,
    "ports_ok": False,
    "dependencies_ok": False,
    "complete_integration_ok": False,
    "errors": []
}

def verify_system_files():
    """Verifica que todos los archivos necesarios existan"""
    logger.info("📁 VERIFICANDO ARCHIVOS DEL SISTEMA")
    logger.info("=" * 50)

    missing_files = []
    for file_info in SYSTEM_CONFIG["test_files"]:
        full_path = Path(file_info["path"])
        if not full_path.exists():
            missing_files.append(file_info["name"])

    if missing_files:
        logger.error("❌ ARCHIVOS FALTANTES:")
        for file in missing_files:
            logger.error(f"   - {file}")
            system_status["errors"].append(f"Archivo faltante: {file}")
        system_status["files_exist"] = False
    else:
        logger.info("✅ TODOS LOS ARCHIVOS EXISTEN")
        system_status["files_exist"] = True
    return system_status["files_exist"]

def verify_code_structure():
    """Verifica la estructura básica del código"""
    logger.info("\n🔧 VERIFICANDO ESTRUCTURA DEL CÓDIGO")
    logger.info("=" * 50)

    all_ok = True

    # Verificar estructura de data_feed.py
    data_feed_path = SYSTEM_CONFIG["shadow_core_path"] / SYSTEM_CONFIG["data_feed_path"]
    if data_feed_path.exists():
        try:
            with open(data_feed_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que tenga las funciones principales
            required_functions = [
                "generate_simulated_alert",
                "handle_socket_events",
                "start_data_feed_server",
                "get_server_status"
            ]

            missing_functions = []
            for func in required_functions:
                if func not in content:
                    missing_functions.append(func)

            if missing_functions:
                logger.error("❌ FUNCIONES FALTANTES EN data_feed.py:")
                for func in missing_functions:
                    logger.error(f"   - {func}")
                    system_status["errors"].append(f"Función faltante en data_feed.py: {func}")
                all_ok = False
            else:
                logger.info("✅ data_feed.py tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed.py: {e}")
            system_status["errors"].append(f"Error al leer data_feed.py: {e}")
            all_ok = False
    else:
        logger.error("❌ data_feed.py no encontrado")
        system_status["errors"].append("data_feed.py no encontrado")
        all_ok = False

    # Verificar estructura de integrate_data_feed.py
    integration_path = SYSTEM_CONFIG["frontend_integration_path"]
    if integration_path.exists():
        try:
            with open(integration_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que tenga las funciones principales
            required_functions = [
                "connect_to_data_feed",
                "process_alert",
                "notify_new_alert",
                "start_data_feed_integration"
            ]

            missing_functions = []
            for func in required_functions:
                if func not in content:
                    missing_functions.append(func)

            if missing_functions:
                logger.error("❌ FUNCIONES FALTANTES EN integrate_data_feed.py:")
                for func in missing_functions:
                    logger.error(f"   - {func}")
                    system_status["errors"].append(f"Función faltante en integrate_data_feed.py: {func}")
                all_ok = False
            else:
                logger.info("✅ integrate_data_feed.py tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer integrate_data_feed.py: {e}")
            system_status["errors"].append(f"Error al leer integrate_data_feed.py: {e}")
            all_ok = False
    else:
        logger.error("❌ integrate_data_feed.py no encontrado")
        system_status["errors"].append("integrate_data_feed.py no encontrado")
        all_ok = False

    # Verificar estructura de data_feed_integration.js
    js_path = SYSTEM_CONFIG["frontend_js_path"]
    if js_path.exists():
        try:
            with open(js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que tenga las funciones principales
            required_functions = [
                "connectToDataFeed",
                "processAlert",
                "notifyNewAlert",
                "startDataFeedIntegration"
            ]

            missing_functions = []
            for func in required_functions:
                if func not in content:
                    missing_functions.append(func)

            if missing_functions:
                logger.error("❌ FUNCIONES FALTANTES EN data_feed_integration.js:")
                for func in missing_functions:
                    logger.error(f"   - {func}")
                    system_status["errors"].append(f"Función faltante en data_feed_integration.js: {func}")
                all_ok = False
            else:
                logger.info("✅ data_feed_integration.js tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed_integration.js: {e}")
            system_status["errors"].append(f"Error al leer data_feed_integration.js: {e}")
            all_ok = False
    else:
        logger.error("❌ data_feed_integration.js no encontrado")
        system_status["errors"].append("data_feed_integration.js no encontrado")
        all_ok = False

    system_status["code_structure_ok"] = all_ok
    return all_ok

def verify_dashboard_config():
    """Verifica la configuración del dashboard OSINT"""
    logger.info("\n📊 VERIFICANDO CONFIGURACIÓN DEL DASHBOARD")
    logger.info("=" * 50)

    dashboard_path = SYSTEM_CONFIG["dashboard_path"]
    if dashboard_path.exists():
        try:
            with open(dashboard_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que tenga los elementos principales
            required_elements = [
                "osint-dashboard",
                "osint-alert-list",
                "osint-alert-item",
                "osint-details-panel",
                "DataFeedIntegration"
            ]

            missing_elements = []
            for element in required_elements:
                if element not in content:
                    missing_elements.append(element)

            if missing_elements:
                logger.error("❌ ELEMENTOS FALTANTES EN el dashboard:")
                for element in missing_elements:
                    logger.error(f"   - {element}")
                    system_status["errors"].append(f"Elemento faltante en dashboard: {element}")
                return False
            else:
                logger.info("✅ Dashboard OSINT tiene la estructura correcta")

                # Verificar que tenga los scripts necesarios
                required_scripts = [
                    "data_feed_integration.js",
                    "osint_globe.js"
                ]

                script_missing = []
                for script in required_scripts:
                    if f"src=\"/static/js/{script}\"" not in content:
                        script_missing.append(script)

                if script_missing:
                    logger.error("❌ SCRIPTS FALTANTES EN el dashboard:")
                    for script in script_missing:
                        logger.error(f"   - {script}")
                        system_status["errors"].append(f"Script faltante en dashboard: {script}")
                    return False
                else:
                    logger.info("✅ Todos los scripts necesarios están incluidos")

            system_status["dashboard_ok"] = True
            return True
        except Exception as e:
            logger.error(f"❌ Error al leer el dashboard: {e}")
            system_status["errors"].append(f"Error al leer dashboard: {e}")
            return False
    else:
        logger.error("❌ Dashboard OSINT no encontrado")
        system_status["errors"].append("Dashboard OSINT no encontrado")
        return False

def verify_knowledge_integration():
    """Verifica la integración con el sistema de nodos de conocimiento"""
    logger.info("\n🌐 VERIFICANDO INTEGRACIÓN CON NODOS DE CONOCIMIENTO")
    logger.info("=" * 50)

    # Verificar que el módulo de integración tenga referencia a KnowledgeNodes
    integration_path = SYSTEM_CONFIG["frontend_integration_path"]
    if integration_path.exists():
        try:
            with open(integration_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que haga referencia a KnowledgeNodes
            if "window.KnowledgeNodes" not in content and "KnowledgeNodes" not in content:
                logger.error("❌ No se encontró referencia a KnowledgeNodes en integrate_data_feed.py")
                system_status["errors"].append("No se encontró referencia a KnowledgeNodes")
                return False
            else:
                logger.info("✅ Referencia a KnowledgeNodes encontrada en integrate_data_feed.py")

            # Verificar que notifique nuevas alertas a KnowledgeNodes
            if "updateThreatState" not in content:
                logger.error("❌ No se encontró notificación a updateThreatState en KnowledgeNodes")
                system_status["errors"].append("No se encontró notificación a updateThreatState")
                return False
            else:
                logger.info("✅ Notificación a updateThreatState encontrada")

            system_status["knowledge_integration_ok"] = True
            return True
        except Exception as e:
            logger.error(f"❌ Error al leer integrate_data_feed.py: {e}")
            system_status["errors"].append(f"Error al leer integrate_data_feed.py: {e}")
            return False
    else:
        logger.error("❌ integrate_data_feed.py no encontrado")
        system_status["errors"].append("integrate_data_feed.py no encontrado")
        return False

def verify_port_configuration():
    """Verifica la configuración de puertos en el sistema"""
    logger.info("\n🔌 VERIFICANDO CONFIGURACIÓN DE PUERTOS")
    logger.info("=" * 50)

    all_ok = True

    # Verificar que el puerto 5002 esté configurado en data_feed.py
    data_feed_path = SYSTEM_CONFIG["shadow_core_path"] / SYSTEM_CONFIG["data_feed_path"]
    if data_feed_path.exists():
        try:
            with open(data_feed_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "5002" not in content:
                logger.error("❌ Puerto 5002 no encontrado en data_feed.py")
                system_status["errors"].append("Puerto 5002 no encontrado en data_feed.py")
                all_ok = False
            else:
                logger.info("✅ Puerto 5002 configurado correctamente en data_feed.py")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed.py: {e}")
            system_status["errors"].append(f"Error al leer data_feed.py: {e}")
            all_ok = False
    else:
        logger.error("❌ data_feed.py no encontrado")
        system_status["errors"].append("data_feed.py no encontrado")
        all_ok = False

    # Verificar que el frontend use el puerto correcto
    js_path = SYSTEM_CONFIG["frontend_js_path"]
    if js_path.exists():
        try:
            with open(js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "5002" not in content:
                logger.error("❌ Puerto 5002 no encontrado en data_feed_integration.js")
                system_status["errors"].append("Puerto 5002 no encontrado en data_feed_integration.js")
                all_ok = False
            else:
                logger.info("✅ Puerto 5002 configurado correctamente en data_feed_integration.js")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed_integration.js: {e}")
            system_status["errors"].append(f"Error al leer data_feed_integration.js: {e}")
            all_ok = False
    else:
        logger.error("❌ data_feed_integration.js no encontrado")
        system_status["errors"].append("data_feed_integration.js no encontrado")
        all_ok = False

    system_status["ports_ok"] = all_ok
    return all_ok

def verify_dependencies():
    """Verifica que las dependencias estén instaladas"""
    logger.info("\n📦 VERIFICANDO DEPENDENCIAS DEL SISTEMA")
    logger.info("=" * 50)

    try:
        # Intentar importar cada dependencia
        missing_deps = []
        for dep in SYSTEM_CONFIG["required_dependencies"]:
            try:
                if dep == "flask-socketio":
                    import flask_socketio
                elif dep == "python-dotenv":
                    from dotenv import load_dotenv
                else:
                    __import__(dep)

                logger.info(f"✅ {dep} está instalado")
            except ImportError:
                missing_deps.append(dep)

        if missing_deps:
            logger.warning("⚠️ DEPENDENCIAS FALTANTES:")
            for dep in missing_deps:
                logger.warning(f"   - {dep}")
                system_status["errors"].append(f"Dependencia faltante: {dep}")
            return False
        else:
            logger.info("✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS")
            system_status["dependencies_ok"] = True
            return True

    except Exception as e:
        logger.error(f"❌ Error al verificar dependencias: {e}")
        system_status["errors"].append(f"Error al verificar dependencias: {e}")
        return False

def verify_complete_integration():
    """Verifica que todos los componentes estén correctamente integrados"""
    logger.info("\n🔗 VERIFICANDO INTEGRACIÓN COMPLETA DEL SISTEMA")
    logger.info("=" * 50)

    # Verificar que todos los componentes estén conectados
    components = [
        ("Shadow-Core", "data_feed.py"),
        ("Shadow-Core", "start_data_feed.py"),
        ("AME_Core", "integrate_data_feed.py"),
        ("AME_Core/static/js", "data_feed_integration.js"),
        ("AME_Core/templates", "osint_dashboard.html"),
        ("ui_engine", "knowledge_nodes.js")
    ]

    all_connected = True
    for component_group, component_file in components:
        component_path = Path(component_group) / component_file
        if not component_path.exists():
            logger.error(f"❌ {component_path} no encontrado")
            system_status["errors"].append(f"Componente no encontrado: {component_path}")
            all_connected = False
        else:
            logger.info(f"✅ {component_path} encontrado")

    if not all_connected:
        system_status["complete_integration_ok"] = False
        return False

    # Verificar que los componentes tengan referencias cruzadas
    try:
        # Leer data_feed.py
        data_feed_path = SYSTEM_CONFIG["shadow_core_path"] / SYSTEM_CONFIG["data_feed_path"]
        with open(data_feed_path, 'r', encoding='utf-8') as f:
            data_feed_content = f.read()

        # Leer integrate_data_feed.py
        integration_path = SYSTEM_CONFIG["frontend_integration_path"]
        with open(integration_path, 'r', encoding='utf-8') as f:
            integration_content = f.read()

        # Verificar que data_feed.py tenga configuración para nodos
        if "node_mapping" not in data_feed_content:
            logger.error("❌ No se encontró configuración node_mapping en data_feed.py")
            system_status["errors"].append("Configuración node_mapping no encontrada en data_feed.py")
            return False

        # Verificar que integrate_data_feed.py use la configuración de nodos
        if "node_mapping" not in integration_content:
            logger.error("❌ No se encontró referencia a node_mapping en integrate_data_feed.py")
            system_status["errors"].append("Referencia a node_mapping no encontrada en integrate_data_feed.py")
            return False

        # Verificar que ambos usen los mismos puertos
        if "5002" not in data_feed_content or "5002" not in integration_content:
            logger.error("❌ Los puertos no coinciden entre data_feed.py e integrate_data_feed.py")
            system_status["errors"].append("Puertos no coinciden entre componentes")
            return False

        logger.info("✅ TODOS LOS COMPONENTES ESTÁN CORRECTAMENTE INTEGRADOS")
        system_status["complete_integration_ok"] = True
        return True

    except Exception as e:
        logger.error(f"❌ Error al verificar integración completa: {e}")
        system_status["errors"].append(f"Error al verificar integración completa: {e}")
        return False

def generate_system_summary():
    """Genera un resumen completo del estado del sistema"""
    logger.info("\n📋 GENERANDO RESUMEN DEL SISTEMA")
    logger.info("=" * 60)

    summary = []
    summary.append("RESUMEN DE INTEGRACIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    summary.append("=" * 60)
    summary.append(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append("")

    # Resultados de las verificaciones
    checks = [
        ("📁 Archivos del sistema", system_status["files_exist"]),
        ("🔧 Estructura del código", system_status["code_structure_ok"]),
        ("📊 Dashboard OSINT", system_status["dashboard_ok"]),
        ("🌐 Integración con nodos", system_status["knowledge_integration_ok"]),
        ("🔌 Configuración de puertos", system_status["ports_ok"]),
        ("📦 Dependencias del sistema", system_status["dependencies_ok"]),
        ("🔗 Integración completa", system_status["complete_integration_ok"])
    ]

    summary.append("📊 ESTADO DEL SISTEMA:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        summary.append(f"   {status} {check_name}")

    # Estadísticas
    success_count = sum(1 for _, result in checks if result)
    total_checks = len(checks)
    summary.append(f"")
    summary.append(f"📊 ESTADÍSTICAS:")
    summary.append(f"   Verificaciones realizadas: {total_checks}")
    summary.append(f"   Verificaciones exitosas: {success_count}")
    summary.append(f"   Porcentaje de éxito: {int((success_count / total_checks) * 100)}%")

    # Errores
    if system_status["errors"]:
        summary.append(f"")
        summary.append(f"⚠️ PROBLEMAS ENCONTRADOS:")
        for error in system_status["errors"]:
            summary.append(f"   - {error}")

    # Conclusión
    summary.append(f"")
    if success_count == total_checks:
        summary.append("🎉 ¡TODO FUNCIONA CORRECTAMENTE!")
        summary.append("   El sistema de datos en tiempo real está listo para su uso.")
        summary.append("")
        summary.append("📋 RECOMENDACIONES:")
        summary.append("   - Inicie el servidor con: python Shadow-Core/start_data_feed.py")
        summary.append("   - Acceda al dashboard OSINT desde el frontend")
        summary.append("   - Verifique la integración con el sistema de nodos de conocimiento")
        summary.append("   - Ejecute pruebas de conexión para confirmar el funcionamiento")
    else:
        summary.append("⚠️ HAY PROBLEMAS QUE DEBEN SER RESUELTOS:")
        summary.append("   Consulte los problemas arriba para más detalles.")
        summary.append("")
        summary.append("🔧 RECOMENDACIONES:")
        summary.append("   1. Verifique que todos los archivos estén en las ubicaciones correctas")
        summary.append("   2. Revisar los logs del servidor para errores")
        summary.append("   3. Instale manualmente las dependencias faltantes si es necesario")
        summary.append("   4. Verifique la configuración de puertos en los archivos de código")
        summary.append("   5. Ejecute el script de verificación de integración para solucionar problemas")

    # Guardar resumen en un archivo
    summary_file = "system_integration_summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(summary))

    logger.info(f"✅ Resumen del sistema generado en: {summary_file}")
    return summary

def main():
    """Función principal"""
    logger.info("RESUMEN DE INTEGRACIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    logger.info("Este script genera un informe completo del estado actual de la integración")

    # Ejecutar todas las verificaciones
    verify_system_files()
    verify_code_structure()
    verify_dashboard_config()
    verify_knowledge_integration()
    verify_port_configuration()
    verify_dependencies()
    verify_complete_integration()

    # Generar resumen del sistema
    summary = generate_system_summary()

    # Mostrar resumen en consola
    for line in summary:
        logger.info(line)

    # Determinar si el sistema está listo
    all_checks_passed = all([
        system_status["files_exist"],
        system_status["code_structure_ok"],
        system_status["dashboard_ok"],
        system_status["knowledge_integration_ok"],
        system_status["ports_ok"],
        system_status["dependencies_ok"],
        system_status["complete_integration_ok"]
    ])

    if all_checks_passed:
        logger.info("\n🎉 ¡EL SISTEMA ESTÁ LISTO PARA SU USO!")
        logger.info("   Todos los componentes están correctamente integrados")
        return True
    else:
        logger.error("\n❌ EL SISTEMA TIENE PROBLEMAS QUE DEBEN SER RESUELTOS")
        logger.info("   Consulte el resumen para más detalles")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)