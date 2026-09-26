#!/usr/bin/env python3
"""
start_sync.py - Script de inicio para el servicio de sincronización en tiempo real.
Este script simplifica el inicio del servicio de sincronización con un solo comando,
verificando la configuración y dependencias antes de iniciar.

Uso:
  python start_sync.py
"""

import os
import sys
import subprocess
import json
import logging
from typing import Dict

def check_dependencies() -> bool:
    """Verifica que todas las dependencias necesarias estén instaladas."""
    required_packages = ["watchdog", "paramiko"]

    try:
        import watchdog
        import paramiko
    except ImportError as e:
        missing_packages = []
        if "watchdog" not in sys.modules:
            missing_packages.append("watchdog")
        if "paramiko" not in sys.modules:
            missing_packages.append("paramiko")

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

def check_config_file(config_file: str = "sync_config.json") -> bool:
    """Verifica que el archivo de configuración exista y sea válido."""
    if not os.path.exists(config_file):
        print(f"❌ Archivo de configuración no encontrado: {config_file}")
        print("Generando configuración por defecto...")
        try:
            import sync_to_mobile
            config = sync_to_mobile.setup_default_config()
            sync_to_mobile.save_config(config, config_file)
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

def check_ssh_connection(config: Dict) -> bool:
    """Verifica que la conexión SSH esté disponible."""
    try:
        command = [
            "ssh", "-p", str(config["ssh_port"]),
            f"{config['ssh_user']}@{config['ssh_host']}",
            "echo 'SSH connection test successful'"
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ Conexión SSH verificada con éxito.")
            return True
        else:
            print(f"❌ Error en la conexión SSH: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error al probar conexión SSH: {str(e)}")
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
    logger = logging.getLogger("StartSync")

    print("🔧 Iniciando configuración del servicio de sincronización en tiempo real...")
    print("=" * 70)

    # Verificar dependencias
    if not check_dependencies():
        print("❌ No se pueden continuar sin las dependencias requeridas.")
        sys.exit(1)

    # Verificar archivo de configuración
    config_file = "sync_config.json"
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

    # Verificar conexión SSH
    if not check_ssh_connection(config):
        print("❌ No se puede continuar sin conexión SSH válida.")
        print("Por favor, verifica que el túnel SSH esté activo y las credenciales sean correctas.")
        sys.exit(1)

    # Verificar que los directorios locales existan
    for watch_dir in config.get("watch_dirs", [config["local_dev_dir"]]):
        if not os.path.exists(watch_dir):
            print(f"❌ Directorio no encontrado: {watch_dir}")
            sys.exit(1)

    print("✅ Todas las verificaciones iniciales completadas con éxito.")
    print("=" * 70)
    print("🚀 Iniciando servicio de sincronización en tiempo real...")
    print(f"   Configuración: {config_file}")
    print(f"   Directorios a monitorear: {', '.join(config.get('watch_dirs', [config['local_dev_dir']]))}")
    print(f"   Conexión SSH: {config['ssh_user']}@{config['ssh_host']}:{config['ssh_port']}")
    print("=" * 70)

    # Iniciar el servicio de sincronización
    try:
        import sync_to_mobile
        service = sync_to_mobile.LiveSyncService(config)
        service.start()
    except KeyboardInterrupt:
        print("\n🛑 Servicio de sincronización detenido por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error al iniciar el servicio de sincronización: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()