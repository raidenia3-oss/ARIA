"""
start_decision_core.py - Script para iniciar el Decision Core de AURA
Este script inicia el motor de decisiones que procesa alertas entrantes
y toma acciones automáticas basadas en reglas de negocio.
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_requirements():
    """Instalar requisitos adicionales para el Decision Core"""
    try:
        logger.info("📦 Instalando requisitos para Decision Core...")

        # Verificar si ya están instalados
        try:
            import socketio
            import dotenv
            logger.info("✅ Requisitos ya están instalados")
            return True
        except ImportError:
            pass

        # Instalar requisitos desde el archivo requirements_decision.txt
        requirements_file = Path("Shadow-Core/requirements_decision.txt")
        if requirements_file.exists():
            logger.info(f"📄 Encontrado archivo de requisitos: {requirements_file}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("✅ Requisitos instalados con éxito")
            logger.info(result.stdout)
            return True
        else:
            logger.error("❌ Archivo de requisitos no encontrado")
            return False

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error al instalar requisitos: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado al instalar requisitos: {e}")
        return False

def start_decision_core():
    """Iniciar el Decision Core"""
    try:
        logger.info("🚀 Iniciando Decision Core para AURA")

        # Verificar si el Decision Core ya está en ejecución
        try:
            import decision_core
            logger.info("✅ Decision Core ya está en ejecución (módulo importado)")
            return True
        except ImportError:
            pass

        # Verificar si el archivo decision_core.py existe
        decision_core_path = Path("AURA_Core/decision_core.py")
        if not decision_core_path.exists():
            logger.error("❌ Archivo decision_core.py no encontrado")
            return False

        # Verificar si el archivo de reglas existe
        rules_file = Path("AURA_Core/decision_rules.json")
        if not rules_file.exists():
            logger.warning("⚠️ Archivo decision_rules.json no encontrado. Usando reglas por defecto.")
            # Crear el archivo con reglas por defecto
            with open(rules_file, 'w', encoding='utf-8') as f:
                import json
                default_rules = {
                    "threat_rules": [
                        {
                            "name": "amenaza_alta_critica",
                            "condition": {
                                "type": "Amenaza",
                                "severity": ["Alta", "Crítica"]
                            },
                            "actions": [
                                {"type": "Notificar", "channel": "security_team", "message": "Alerta crítica detectada: {{title}}"}
                            ]
                        }
                    ],
                    "default_actions": [
                        {"type": "Registrar_Evento", "event": "alert_processed"}
                    ]
                }
                json.dump(default_rules, f, indent=4, ensure_ascii=False)
            logger.info("✅ Archivo de reglas creado con valores por defecto")

        # Iniciar el Decision Core
        logger.info("🔌 Conectando Decision Core al servidor...")
        import decision_core
        decision_core.main()

        return True

    except Exception as e:
        logger.error(f"❌ Error al iniciar Decision Core: {e}")
        return False

def main():
    """Función principal"""
    logger.info("INICIANDO DECISION CORE PARA AURA")
    logger.info("=" * 50)

    # Instalar requisitos
    if not install_requirements():
        logger.error("❌ No se pudieron instalar los requisitos. Deteniendo ejecución.")
        return False

    # Iniciar Decision Core
    if not start_decision_core():
        logger.error("❌ No se pudo iniciar Decision Core.")
        return False

    logger.info("")
    logger.info("🎉 Decision Core iniciado con éxito!")
    logger.info("   - Procesando alertas entrantes")
    logger.info("   - Tomando decisiones automáticas")
    logger.info("   - Registrando acciones en logs")
    logger.info("   - Reportando estado al dashboard")
    logger.info("")
    logger.info("Para detener el Decision Core, presione Ctrl+C")

    try:
        # Mantener el script en ejecución
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Decision Core detenido por el usuario")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)