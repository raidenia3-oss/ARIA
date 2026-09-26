#!/usr/bin/env python3
"""
start_hot_reload.py - Script de inicio para el servicio de Hot-Reload.
Este script simplifica el inicio del servicio de Hot-Reload con un solo comando,
verificando la configuración y dependencias antes de iniciar.

Uso:
  python start_hot_reload.py
"""

import os
import sys
import subprocess
import json
import logging
from typing import Dict

def check_dependencies() -> bool:
    """Verifica que todas las dependencias necesarias estén instaladas."""
    required_packages = ["watchdog"]

    try:
        import watchdog
    except ImportError as e:
        missing_packages = []
        if "watchdog" not in sys.modules:
            missing_packages.append("watchdog")

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

def check_config_file(config_file: str = "hot_reload_config.json") -> bool:
    """Verifica que el archivo de configuración exista y sea válido."""
    if not os.path.exists(config_file):
        print(f"❌ Archivo de configuración no encontrado: {config_file}")
        print("Generando configuración por defecto...")
        try:
            import hot_reload_server
            config = hot_reload_server.setup_default_config()
            hot_reload_server.save_config(config, config_file)
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

def check_directory_exists(config: Dict) -> bool:
    """Verifica que el directorio de AME exista."""
    ame_dir = config.get("ame_frontend_dir", "AME_Core")
    if not os.path.exists(ame_dir):
        print(f"❌ Directorio no encontrado: {ame_dir}")
        return False
    return True

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
    logger = logging.getLogger("StartHotReload")

    print("🔧 Iniciando configuración del servicio de Hot-Reload...")
    print("=" * 70)

    # Verificar dependencias
    if not check_dependencies():
        print("❌ No se pueden continuar sin las dependencias requeridas.")
        sys.exit(1)

    # Verificar archivo de configuración
    config_file = "hot_reload_config.json"
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

    # Verificar que el directorio de AME exista
    if not check_directory_exists(config):
        print("❌ No se puede continuar sin el directorio de AME.")
        sys.exit(1)

    print("✅ Todas las verificaciones iniciales completadas con éxito.")
    print("=" * 70)
    print("🚀 Iniciando servicio de Hot-Reload...")
    print(f"   Configuración: {config_file}")
    print(f"   Directorios a monitorear: {config['ame_frontend_dir']}")
    print(f"   Puerto WebSocket: ws://{config['websocket_host']}:{config['websocket_port']}")
    print("=" * 70)

    # Iniciar el servicio de Hot-Reload
    try:
        import hot_reload_server
        service = hot_reload_server.HotReloadService(config)

        # Iniciar el servicio en un hilo separado para permitir el manejo de señales
        import threading
        hot_reload_thread = threading.Thread(target=service.start, daemon=True)
        hot_reload_thread.start()

        # Esperar a que el hilo termine (para manejo de señales)
        hot_reload_thread.join()

    except KeyboardInterrupt:
        print("\n🛑 Servicio de Hot-Reload detenido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error al iniciar el servicio de Hot-Reload: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()