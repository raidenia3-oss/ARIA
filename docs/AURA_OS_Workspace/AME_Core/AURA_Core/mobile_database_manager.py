#!/usr/bin/env python3
"""
mobile_database_manager.py - Módulo para gestionar la base de datos SQLite en el dispositivo móvil.
Este módulo permite ejecutar queries SQL en la base de datos remota (aura_intel.db) desde la PC
y recibir los resultados de vuelta.

Características:
- Conexión SSH al dispositivo móvil.
- Ejecución de queries SQL en la base de datos remota.
- Retorno de resultados en formato JSON.
- Logging detallado para monitoreo.
"""

import os
import sys
import subprocess
import json
import logging
import sqlite3
from typing import Dict, List, Any, Optional, Union
import tempfile
import shutil
from datetime import datetime

class MobileDatabaseManager:
    """Gestor de la base de datos SQLite en el dispositivo móvil."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.ssh_host = config.get("ssh_host", "localhost")
        self.ssh_port = config.get("ssh_port", 8022)
        self.ssh_user = config.get("ssh_user", "user")
        self.temp_dir = tempfile.mkdtemp()
        self.db_backup_path = os.path.join(self.temp_dir, "aura_intel_backup.db")

    def _setup_logging(self):
        """Configura el logging para el gestor de base de datos."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('mobile_database_manager.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("MobileDatabaseManager")
        logger.setLevel(logging.INFO)
        return logger

    def _execute_ssh_command(self, command: List[str]) -> str:
        """Ejecuta un comando SSH en el dispositivo móvil y devuelve la salida."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.get("ssh_timeout", 30)
            )
            if result.returncode != 0:
                error_msg = f"Error al ejecutar comando SSH: {result.stderr}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            return result.stdout
        except Exception as e:
            self.logger.error(f"Error al ejecutar comando SSH: {str(e)}")
            raise

    def _copy_database(self, action: str = "pull") -> str:
        """Copia la base de datos desde/ hacia el dispositivo móvil."""
        try:
            if action == "pull":
                # Copiar la base de datos desde el móvil a la PC (para consultas)
                command = [
                    "scp",
                    f"-P", str(self.ssh_port),
                    f"{self.ssh_user}@{self.ssh_host}:{self.db_path}",
                    self.db_backup_path
                ]
                self.logger.info(f"Copiando base de datos desde el móvil a {self.db_backup_path}")
            elif action == "push":
                # Copiar la base de datos desde la PC al móvil (para actualizaciones)
                command = [
                    "scp",
                    f"-P", str(self.ssh_port),
                    self.db_backup_path,
                    f"{self.ssh_user}@{self.ssh_host}:{self.db_path}"
                ]
                self.logger.info(f"Copiando base de datos desde {self.db_backup_path} al móvil")
            else:
                raise ValueError(f"Acción no válida: {action}")

            result = self._execute_ssh_command(command)
            self.logger.debug(f"Resultado de copia: {result}")
            return self.db_backup_path

        except Exception as e:
            self.logger.error(f"Error al copiar la base de datos: {str(e)}")
            raise

    def _ensure_database_exists(self) -> bool:
        """Verifica que la base de datos exista en el dispositivo móvil."""
        try:
            # Intentar copiar la base de datos para verificar su existencia
            self._copy_database("pull")
            return True
        except Exception as e:
            self.logger.warning(f"Base de datos no encontrada en el móvil: {str(e)}")
            return False

    def _create_database_schema(self) -> None:
        """Crea el esquema de la base de datos en el dispositivo móvil."""
        try:
            # Copiar la base de datos local (si existe) al móvil
            local_db_path = os.path.join(os.path.dirname(__file__), "aura_intel_schema.db")
            if os.path.exists(local_db_path):
                self._copy_database("push")
                self.logger.info("Esquema de base de datos copiado al dispositivo móvil.")
            else:
                self.logger.warning("No se encontró el esquema local de la base de datos.")
                # Crear una base de datos temporal con el esquema
                self._create_local_schema()
                self._copy_database("push")
                self.logger.info("Esquema de base de datos creado y copiado al dispositivo móvil.")

        except Exception as e:
            self.logger.error(f"Error al crear el esquema de la base de datos: {str(e)}")
            raise

    def _create_local_schema(self) -> None:
        """Crea una base de datos local con el esquema definido."""
        try:
            # Crear una base de datos temporal con el esquema
            conn = sqlite3.connect(self.db_backup_path)
            cursor = conn.cursor()

            # Crear tablas necesarias para el sistema AURA
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    source_ip TEXT,
                    target TEXT,
                    status TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS osint_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    target TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    confidence INTEGER,
                    source TEXT,
                    processed BOOLEAN DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    battery_level REAL,
                    memory_usage REAL,
                    cpu_usage REAL,
                    connection_status TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    node_id TEXT,
                    target TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at DATETIME
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS module_execution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_name TEXT NOT NULL,
                    execution_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    duration_seconds REAL,
                    output TEXT,
                    error TEXT,
                    node_id TEXT,
                    parameters TEXT
                )
            """)

            # Crear índices para mejorar el rendimiento
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_logs_timestamp ON node_logs(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_logs_node_id ON node_logs(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_node_logs_tool_name ON node_logs(tool_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_osint_results_target ON osint_results(target)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_osint_results_tool_name ON osint_results(tool_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_osint_results_timestamp ON osint_results(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_module_execution_module_name ON module_execution(module_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_module_execution_timestamp ON module_execution(execution_time)")

            conn.commit()
            conn.close()
            self.logger.info("Esquema de base de datos creado localmente.")

        except Exception as e:
            self.logger.error(f"Error al crear el esquema local de la base de datos: {str(e)}")
            raise

    def initialize_database(self) -> bool:
        """Inicializa la base de datos en el dispositivo móvil si no existe."""
        try:
            if not self._ensure_database_exists():
                self._create_database_schema()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error al inicializar la base de datos: {str(e)}")
            raise

    def execute_query(self, query: str, params: Optional[Union[Dict, List, Tuple]] = None) -> List[Dict]:
        """Ejecuta una consulta SQL en la base de datos remota y devuelve los resultados."""
        try:
            # Copiar la base de datos desde el móvil
            db_path = self._copy_database("pull")

            # Conectar a la base de datos local
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Ejecutar la consulta
            if params:
                if isinstance(params, dict):
                    cursor.execute(query, params)
                else:
                    cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Obtener los resultados
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()

            # Limpiar la copia local
            os.remove(db_path)

            return results

        except Exception as e:
            # Limpiar la copia local en caso de error
            if os.path.exists(db_path):
                os.remove(db_path)
            self.logger.error(f"Error al ejecutar consulta: {str(e)}")
            raise

    def execute_transaction(self, queries: List[Dict]) -> bool:
        """Ejecuta una transacción con múltiples consultas en la base de datos remota."""
        try:
            # Copiar la base de datos desde el móvil
            db_path = self._copy_database("pull")

            # Conectar a la base de datos local
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Ejecutar cada consulta en la transacción
            for query_data in queries:
                query = query_data["query"]
                params = query_data.get("params")

                if params:
                    if isinstance(params, dict):
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query, params)
                else:
                    cursor.execute(query)

            conn.commit()
            conn.close()

            # Copiar la base de datos actualizada de vuelta al móvil
            self._copy_database("push")
            return True

        except Exception as e:
            # Limpiar la copia local en caso de error
            if os.path.exists(db_path):
                os.remove(db_path)
            self.logger.error(f"Error al ejecutar transacción: {str(e)}")
            return False

    def backup_database(self, backup_path: str) -> bool:
        """Realiza una copia de seguridad de la base de datos en el dispositivo móvil."""
        try:
            # Copiar la base de datos desde el móvil
            db_path = self._copy_database("pull")

            # Copiar la base de datos local a la ruta de destino
            shutil.copy2(db_path, backup_path)

            # Limpiar la copia local
            os.remove(db_path)

            return True
        except Exception as e:
            # Limpiar la copia local en caso de error
            if os.path.exists(db_path):
                os.remove(db_path)
            self.logger.error(f"Error al realizar copia de seguridad: {str(e)}")
            raise

    def restore_database(self, backup_path: str) -> bool:
        """Restaura la base de datos desde una copia de seguridad en el dispositivo móvil."""
        try:
            # Copiar la base de datos de respaldo al móvil
            self._copy_database("push", backup_path)
            return True
        except Exception as e:
            self.logger.error(f"Error al restaurar la base de datos: {str(e)}")
            raise

    def close(self):
        """Limpia recursos temporales."""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            self.logger.error(f"Error al limpiar recursos temporales: {str(e)}")

    def __enter__(self):
        """Contexto para el manejo de recursos."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra los recursos al salir del contexto."""
        self.close()

def load_config(config_file: str = "mobile_database_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "mobile_database_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el gestor de base de datos."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el gestor de base de datos móvil AURA",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "ssh_timeout": 30,
        "log_file": "mobile_database_manager.log",
        "schema_file": "aura_intel_schema.db"
    }

def main():
    """Punto de entrada principal para pruebas del gestor de base de datos."""
    parser = argparse.ArgumentParser(description="Gestor de base de datos SQLite en el dispositivo móvil.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="mobile_database_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--init", action="store_true", help="Inicializar la base de datos en el móvil")
    parser.add_argument("--query", help="Ejecutar una consulta SQL")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("Configuración por defecto guardada en mobile_database_config.json")
            return

        config = load_config(args.config)
        db_manager = MobileDatabaseManager(config)

        if args.init:
            print("Inicializando base de datos en el dispositivo móvil...")
            db_manager.initialize_database()
            print("Base de datos inicializada con éxito.")
            return

        if args.query:
            print(f"Ejecutando consulta: {args.query}")
            results = db_manager.execute_query(args.query)
            print(f"Resultado de la consulta ({len(results)} registros):")
            for row in results:
                print(row)
            return

        print("Gestor de base de datos listo para uso.")
        print("Ejemplos de uso:")
        print("  python mobile_database_manager.py --init (Inicializar base de datos)")
        print("  python mobile_database_manager.py --query \"SELECT * FROM node_logs LIMIT 5\"")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    main()