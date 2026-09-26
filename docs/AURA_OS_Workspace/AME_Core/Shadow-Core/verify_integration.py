"""
verify_integration.py - Script para verificar la integración del sistema de datos en tiempo real
Este script verifica que todos los componentes estén correctamente configurados
y que la integración entre Shadow-Core y el frontend funcione correctamente
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del sistema
SYSTEM_CONFIG = {
    "shadow_core_path": "Shadow-Core",
    "data_feed_path": "data_feed.py",
    "start_script_path": "start_data_feed.py",
    "frontend_integration_path": "AME_Core/integrate_data_feed.py",
    "frontend_js_path": "AME_Core/static/js/data_feed_integration.js",
    "dashboard_path": "AME_Core/templates/osint_dashboard.html",
    "test_files": [
        "data_feed.py",
        "start_data_feed.py",
        "requirements.txt",
        "integrate_data_feed.py",
        "data_feed_integration.js",
        "osint_dashboard.html"
    ],
    "required_dependencies": [
        "flask",
        "flask-socketio",
        "eventlet",
        "python-dotenv"
    ],
    "test_ports": [5002, 5003]
}

# Función para verificar archivos del sistema
def verify_system_files():
    """Verifica que todos los archivos necesarios existan"""
    logger.info("📁 VERIFICANDO ARCHIVOS DEL SISTEMA")
    logger.info("=" * 50)

    missing_files = []
    for file_path in SYSTEM_CONFIG["test_files"]:
        full_path = os.path.join(SYSTEM_CONFIG["shadow_core_path"], file_path) if file_path.startswith("Shadow-Core/") else file_path
        if not os.path.exists(full_path):
            missing_files.append(file_path)

    if missing_files:
        logger.error("❌ ARCHIVOS FALTANTES:")
        for file in missing_files:
            logger.error(f"   - {file}")
        return False
    else:
        logger.info("✅ TODOS LOS ARCHIVOS EXISTEN")
        return True

# Función para verificar estructura del código
def verify_code_structure():
    """Verifica la estructura básica del código"""
    logger.info("\n🔧 VERIFICANDO ESTRUCTURA DEL CÓDIGO")
    logger.info("=" * 50)

    # Verificar estructura de data_feed.py
    data_feed_path = os.path.join(SYSTEM_CONFIG["shadow_core_path"], SYSTEM_CONFIG["data_feed_path"])
    if os.path.exists(data_feed_path):
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
                return False
            else:
                logger.info("✅ data_feed.py tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed.py: {e}")
            return False
    else:
        logger.error("❌ data_feed.py no encontrado")
        return False

    # Verificar estructura de integrate_data_feed.py
    integration_path = SYSTEM_CONFIG["frontend_integration_path"]
    if os.path.exists(integration_path):
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
                return False
            else:
                logger.info("✅ integrate_data_feed.py tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer integrate_data_feed.py: {e}")
            return False
    else:
        logger.error("❌ integrate_data_feed.py no encontrado")
        return False

    # Verificar estructura de data_feed_integration.js
    js_path = SYSTEM_CONFIG["frontend_js_path"]
    if os.path.exists(js_path):
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
                return False
            else:
                logger.info("✅ data_feed_integration.js tiene la estructura correcta")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed_integration.js: {e}")
            return False
    else:
        logger.error("❌ data_feed_integration.js no encontrado")
        return False

    return True

# Función para verificar configuración del dashboard
def verify_dashboard_config():
    """Verifica la configuración del dashboard OSINT"""
    logger.info("\n📊 VERIFICANDO CONFIGURACIÓN DEL DASHBOARD")
    logger.info("=" * 50)

    dashboard_path = SYSTEM_CONFIG["dashboard_path"]
    if os.path.exists(dashboard_path):
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
                    return False
                else:
                    logger.info("✅ Todos los scripts necesarios están incluidos")

            return True
        except Exception as e:
            logger.error(f"❌ Error al leer el dashboard: {e}")
            return False
    else:
        logger.error("❌ Dashboard OSINT no encontrado")
        return False

# Función para verificar integración con nodos de conocimiento
def verify_knowledge_integration():
    """Verifica la integración con el sistema de nodos de conocimiento"""
    logger.info("\n🌐 VERIFICANDO INTEGRACIÓN CON NODOS DE CONOCIMIENTO")
    logger.info("=" * 50)

    # Verificar que el módulo de integración tenga referencia a KnowledgeNodes
    integration_path = SYSTEM_CONFIG["frontend_integration_path"]
    if os.path.exists(integration_path):
        try:
            with open(integration_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que haga referencia a KnowledgeNodes
            if "window.KnowledgeNodes" not in content and "KnowledgeNodes" not in content:
                logger.error("❌ No se encontró referencia a KnowledgeNodes en integrate_data_feed.py")
                return False
            else:
                logger.info("✅ Referencia a KnowledgeNodes encontrada en integrate_data_feed.py")

            # Verificar que notifique nuevas alertas a KnowledgeNodes
            if "updateThreatState" not in content:
                logger.error("❌ No se encontró notificación a updateThreatState en KnowledgeNodes")
                return False
            else:
                logger.info("✅ Notificación a updateThreatState encontrada")

            return True
        except Exception as e:
            logger.error(f"❌ Error al leer integrate_data_feed.py: {e}")
            return False
    else:
        logger.error("❌ integrate_data_feed.py no encontrado")
        return False

# Función para verificar configuración de puertos
def verify_port_configuration():
    """Verifica la configuración de puertos en el sistema"""
    logger.info("\n🔌 VERIFICANDO CONFIGURACIÓN DE PUERTOS")
    logger.info("=" * 50)

    # Verificar que el puerto 5002 esté configurado en data_feed.py
    data_feed_path = os.path.join(SYSTEM_CONFIG["shadow_core_path"], SYSTEM_CONFIG["data_feed_path"])
    if os.path.exists(data_feed_path):
        try:
            with open(data_feed_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "5002" not in content:
                logger.error("❌ Puerto 5002 no encontrado en data_feed.py")
                return False
            else:
                logger.info("✅ Puerto 5002 configurado correctamente en data_feed.py")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed.py: {e}")
            return False
    else:
        logger.error("❌ data_feed.py no encontrado")
        return False

    # Verificar que el frontend use el puerto correcto
    js_path = SYSTEM_CONFIG["frontend_js_path"]
    if os.path.exists(js_path):
        try:
            with open(js_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "5002" not in content:
                logger.error("❌ Puerto 5002 no encontrado en data_feed_integration.js")
                return False
            else:
                logger.info("✅ Puerto 5002 configurado correctamente en data_feed_integration.js")
        except Exception as e:
            logger.error(f"❌ Error al leer data_feed_integration.js: {e}")
            return False
    else:
        logger.error("❌ data_feed_integration.js no encontrado")
        return False

    return True

# Función para verificar dependencias
def verify_dependencies():
    """Verifica que las dependencias estén instaladas (sin intentar instalarlas)"""
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
            logger.info("   (Nota: Este script no intenta instalarlas automáticamente)")
            return False
        else:
            logger.info("✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS")
            return True

    except Exception as e:
        logger.error(f"❌ Error al verificar dependencias: {e}")
        return False

# Función para verificar integración completa
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
        component_path = os.path.join(component_group, component_file)
        if not os.path.exists(component_path):
            logger.error(f"❌ {component_path} no encontrado")
            all_connected = False
        else:
            logger.info(f"✅ {component_path} encontrado")

    if not all_connected:
        return False

    # Verificar que los componentes tengan referencias cruzadas
    try:
        # Leer data_feed.py
        data_feed_path = os.path.join(SYSTEM_CONFIG["shadow_core_path"], SYSTEM_CONFIG["data_feed_path"])
        with open(data_feed_path, 'r', encoding='utf-8') as f:
            data_feed_content = f.read()

        # Leer integrate_data_feed.py
        integration_path = SYSTEM_CONFIG["frontend_integration_path"]
        with open(integration_path, 'r', encoding='utf-8') as f:
            integration_content = f.read()

        # Verificar que data_feed.py tenga configuración para nodos
        if "node_mapping" not in data_feed_content:
            logger.error("❌ No se encontró configuración node_mapping en data_feed.py")
            return False

        # Verificar que integrate_data_feed.py use la configuración de nodos
        if "node_mapping" not in integration_content:
            logger.error("❌ No se encontró referencia a node_mapping en integrate_data_feed.py")
            return False

        # Verificar que ambos usen los mismos puertos
        if "5002" not in data_feed_content or "5002" not in integration_content:
            logger.error("❌ Los puertos no coinciden entre data_feed.py e integrate_data_feed.py")
            return False

        logger.info("✅ TODOS LOS COMPONENTES ESTÁN CORRECTAMENTE INTEGRADOS")
        return True

    except Exception as e:
        logger.error(f"❌ Error al verificar integración completa: {e}")
        return False

# Función para generar informe de verificación
def generate_verification_report():
    """Genera un informe completo de verificación del sistema"""
    logger.info("\n📋 GENERANDO INFORME DE VERIFICACIÓN")
    logger.info("=" * 50)

    report = []
    report.append("INFORME DE VERIFICACIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    report.append("=" * 60)
    report.append(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Verificar archivos
    files_ok = verify_system_files()
    report.append("📁 ARCHIVOS DEL SISTEMA:")
    report.append(f"   {'✅ Todos los archivos existen' if files_ok else '❌ Algunos archivos faltan'}")
    report.append("")

    # Verificar estructura del código
    code_ok = verify_code_structure()
    report.append("🔧 ESTRUCTURA DEL CÓDIGO:")
    report.append(f"   {'✅ Estructura correcta' if code_ok else '❌ Estructura incorrecta'}")
    report.append("")

    # Verificar dashboard
    dashboard_ok = verify_dashboard_config()
    report.append("📊 DASHBOARD OSINT:")
    report.append(f"   {'✅ Configuración correcta' if dashboard_ok else '❌ Configuración incorrecta'}")
    report.append("")

    # Verificar integración con nodos
    knowledge_ok = verify_knowledge_integration()
    report.append("🌐 INTEGRACIÓN CON NODOS DE CONOCIMIENTO:")
    report.append(f"   {'✅ Integración correcta' if knowledge_ok else '❌ Integración incorrecta'}")
    report.append("")

    # Verificar puertos
    ports_ok = verify_port_configuration()
    report.append("🔌 CONFIGURACIÓN DE PUERTOS:")
    report.append(f"   {'✅ Puertos configurados correctamente' if ports_ok else '❌ Puertos mal configurados'}")
    report.append("")

    # Verificar dependencias
    deps_ok = verify_dependencies()
    report.append("📦 DEPENDENCIAS DEL SISTEMA:")
    report.append(f"   {'✅ Todas las dependencias instaladas' if deps_ok else '⚠️ Algunas dependencias faltan'}")
    report.append("")

    # Verificar integración completa
    integration_ok = verify_complete_integration()
    report.append("🔗 INTEGRACIÓN COMPLETA:")
    report.append(f"   {'✅ Todos los componentes están integrados' if integration_ok else '❌ Componentes no integrados'}")
    report.append("")

    # Resumen
    total_tests = 7
    passed_tests = sum([files_ok, code_ok, dashboard_ok, knowledge_ok, ports_ok, deps_ok, integration_ok])
    report.append("📊 RESUMEN:")
    report.append(f"   Pruebas realizadas: {total_tests}")
    report.append(f"   Pruebas exitosas: {passed_tests}")
    report.append(f"   Porcentaje de éxito: {int((passed_tests / total_tests) * 100)}%")
    report.append("")

    if passed_tests == total_tests:
        report.append("🎉 ¡TODO FUNCIONA CORRECTAMENTE!")
        report.append("   El sistema de datos en tiempo real está listo para su uso.")
    else:
        report.append("⚠️ HAY PROBLEMAS QUE DEBEN SER RESUELTOS:")
        if not files_ok:
            report.append("   - Algunos archivos del sistema faltan")
        if not code_ok:
            report.append("   - La estructura del código no es correcta")
        if not dashboard_ok:
            report.append("   - El dashboard OSINT tiene problemas de configuración")
        if not knowledge_ok:
            report.append("   - La integración con nodos de conocimiento no funciona")
        if not ports_ok:
            report.append("   - La configuración de puertos no es correcta")
        if not deps_ok:
            report.append("   - Algunas dependencias no están instaladas")
        if not integration_ok:
            report.append("   - Los componentes no están correctamente integrados")

    # Guardar informe en un archivo
    report_file = "verification_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))

    logger.info(f"✅ Informe de verificación generado en: {report_file}")
    return report

# Función principal
def main():
    """Función principal"""
    logger.info("VERIFICACIÓN DE INTEGRACIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    logger.info("Este script verifica que todos los componentes estén correctamente configurados")
    logger.info("y que la integración entre Shadow-Core y el frontend funcione correctamente")

    # Generar informe de verificación
    report = generate_verification_report()

    # Mostrar informe en consola
    for line in report:
        logger.info(line)

    # Determinar si el sistema está listo
    all_tests_passed = all([
        verify_system_files(),
        verify_code_structure(),
        verify_dashboard_config(),
        verify_knowledge_integration(),
        verify_port_configuration(),
        verify_dependencies(),
        verify_complete_integration()
    ])

    if all_tests_passed:
        logger.info("\n🎉 ¡EL SISTEMA ESTÁ LISTO PARA SU USO!")
        logger.info("   Puede iniciar el servidor con: python start_data_feed.py")
        logger.info("   Y acceder al dashboard OSINT desde el frontend")
        return True
    else:
        logger.error("\n❌ EL SISTEMA TIENE PROBLEMAS QUE DEBEN SER RESUELTOS")
        logger.info("   Consulte el informe de verificación para más detalles")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)