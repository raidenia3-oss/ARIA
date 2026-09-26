#!/usr/bin/env python3
"""
start_mobile_database.py - Script de inicio para el gestor de base de datos móvil.
Este script simplifica el inicio del gestor de base de datos con un solo comando,
verificando la configuración y dependencias antes de iniciar.

Uso:
  python start_mobile_database.py [--init] [--query "SQL_QUERY"]
"""

import os
import sys
import subprocess
import json
import logging
from typing import Dict

def check_dependencies() -> bool:
    """Verifica que todas las dependencias necesarias estén instaladas."""
    required_packages = ["sqlite3"]

    # sqlite3 es parte del estándar de Python, no es necesario instalarlo
    # Solo verificamos que esté disponible
    try:
        import sqlite3
    except ImportError as e:
        print(f"❌ Error: La librería sqlite3 no está disponible: {str(e)}")
        return False

    return True

def check_config_file(config_file: str = "mobile_database_config.json") -> bool:
    """Verifica que el archivo de configuración exista y sea válido."""
    if not os.path.exists(config_file):
        print(f"❌ Archivo de configuración no encontrado: {config_file}")
        print("Generando configuración por defecto...")
        try:
            import mobile_database_manager
            config = mobile_database_manager.setup_default_config()
            mobile_database_manager.save_config(config, config_file)
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
    logger = logging.getLogger("StartMobileDatabase")

    print("🔧 Iniciando configuración del gestor de base de datos móvil...")
    print("=" * 70)

    # Verificar dependencias
    if not check_dependencies():
        print("❌ No se pueden continuar sin las dependencias requeridas.")
        sys.exit(1)

    # Verificar archivo de configuración
    config_file = "mobile_database_config.json"
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
    print("🚀 Gestor de base de datos móvil listo para uso.")
    print(f"   Configuración: {config_file}")
    print(f"   Base de datos: {config['db_path']}")
    print(f"   Host SSH: {config['ssh_host']}:{config['ssh_port']}")
    print("=" * 70)

    # Importar y usar el gestor de base de datos
    try:
        import mobile_database_manager
        db_manager = mobile_database_manager.MobileDatabaseManager(config)

        # Manejar argumentos de línea de comandos
        import argparse
        parser = argparse.ArgumentParser(description="Gestor de base de datos SQLite en el dispositivo móvil.")
        parser.add_argument("--init", action="store_true", help="Inicializar la base de datos en el móvil")
        parser.add_argument("--query", help="Ejecutar una consulta SQL")
        args = parser.parse_args()

        if args.init:
            print("Inicializando base de datos en el dispositivo móvil...")
            db_manager.initialize_database()
            print("✅ Base de datos inicializada con éxito.")
            return

        if args.query:
            print(f"Ejecutando consulta: {args.query}")
            try:
                results = db_manager.execute_query(args.query)
                print(f"✅ Resultado de la consulta ({len(results)} registros):")
                for row in results:
                    print(row)
            except Exception as e:
                print(f"❌ Error al ejecutar consulta: {str(e)}")
                sys.exit(1)
            return

        print("Ejemplos de uso:")
        print("  python start_mobile_database.py --init (Inicializar base de datos)")
        print("  python start_mobile_database.py --query \"SELECT * FROM node_logs LIMIT 5\"")
        print("  python start_mobile_database.py (Modo interactivo)")

        # Modo interactivo
        while True:
            print("\nIngrese una consulta SQL (o 'exit' para salir):")
            query = input("> ")
            if query.lower() in ['exit', 'quit', 'q']:
                break

            if not query.strip():
                continue

            try:
                results = db_manager.execute_query(query)
                print(f"\n✅ Resultado de la consulta ({len(results)} registros):")
                for row in results:
                    print(row)
            except Exception as e:
                print(f"❌ Error al ejecutar consulta: {str(e)}")

    except Exception as e:
        print(f"❌ Error al iniciar el gestor de base de datos: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()