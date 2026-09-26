#!/usr/bin/env python3
"""
start_connection_supervisor.py - Script de inicio para el supervisor de conexión SSH.
Este script simplifica el inicio del supervisor de conexión con un solo comando,
verificando la configuración y dependencias antes de iniciar.

Uso:
  python start_connection_supervisor.py
"""

import os
import sys
import subprocess
import json
import logging
from typing import Dict

def check_dependencies() -> bool:
    """Verifica que todas las dependencias necesarias estén instaladas."""
    required_packages = ["requests"]

    try:
        import requests
    except ImportError as e:
        missing_packages = []
        if "requests" not in sys.modules:
            missing_packages.append("requests")

        if missing_packages:
            print(f"❌ Dependencias faltantes: {', '.join(missing_packages)}")
            print("Instalando dependencias con pip...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
                print("✅ Dependencias instaladas correctamente.")
                return check_dependencies()  # Reintentar después de la instalación
            except subprocess.CalledProcessError:
                print("❌ Error al instalar dependencias. Verifica tu conexión a internet.")
                return False
        return False

    return True

def check_config_file(config_file: str = "connection_supervisor_config.json") -> bool:
    """Verifica que el archivo de configuración exista y sea válido."""
    if not os.path.exists(config_file):
        print(f"❌ Archivo de configuración no encontrado: {config_file}")
        print("Generando configuración por defecto...")
        try:
            import connection_supervisor
            config = connection_supervisor.setup_default_config()
            connection_supervisor.save_config(config, config_file)
            print(f"✅ Configuración por defecto generada en {config_file}")
            return True
        except Exception as e:
            print(f"❌ Error al generar configuración por defecto: {str(e)}")
            return False

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return True
    except Exception as e:
        print(f"❌ Error al leer el archivo de configuración: {str(e)}")
        return False

def setup_logging():
    """Configura el logging básico para el script de inicio."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

def main():
    """Punto de entrada principal del script de inicio."""
    setup_logging()
    logger = logging.getLogger("StartConnectionSupervisor")

    print("🔧 Iniciando configuración del supervisor de conexión SSH...")
    print("=" * 70)

    # Verificar dependencias
    if not check_dependencies():
        print("❌ No se pueden continuar sin las dependencias requeridas.")
        sys.exit(1)

    # Verificar archivo de configuración
    config_file = "connection_supervisor_config.json"
    if not check_config_file(config_file):
        print("❌ No se puede continuar sin una configuración válida.")
        sys.exit(1)

    # Cargar configuración
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error al cargar configuración: {str(e)}")
        sys.exit(1)

    print("✅ Todas las verificaciones iniciales completadas con éxito.")
    print("=" * 70)
    print("🚀 Iniciando supervisor de conexión SSH...")
    print(f"   Configuración: {config_file}")
    print(f"   Host: {config['ssh_host']}:{config['ssh_port']}")
    print(f"   Usuario: {config['ssh_user']}")
    print(f"   Ping intervalo: {config['ping_interval']} segundos")
    print("=" * 70)

    # Iniciar el supervisor de conexión
    try:
        import connection_supervisor
        supervisor = connection_supervisor.ConnectionSupervisor(config)

        # Iniciar el supervisor en un hilo separado para permitir el manejo de señales
        import threading
        supervisor_thread = threading.Thread(target=supervisor.start, daemon=True)
        supervisor_thread.start()

        # Esperar a que el hilo termine (para manejo de señales)
        supervisor_thread.join()

    except KeyboardInterrupt:
        print("\n🛑 Supervisor de conexión detenido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error al iniciar el supervisor de conexión: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()