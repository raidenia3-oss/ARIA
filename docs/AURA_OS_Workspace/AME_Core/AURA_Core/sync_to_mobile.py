#!/usr/bin/env python3
"""
sync_to_mobile.py - Servicio de sincronización en tiempo real para AURA/AME.
Este script monitorea cambios en los directorios de desarrollo (AURA_Core y AME_Core)
y sincroniza automáticamente los archivos modificados al dispositivo móvil vía rsync
a través del túnel SSH/Termux existente.

Características:
- Usa watchdog para detectar cambios en archivos.
- Ignora directorios pesados (.git, node_modules, etc.).
- Ejecuta rsync solo para archivos modificados.
- Logging detallado para monitoreo.
"""

import os
import sys
import time
import logging
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List, Dict, Optional
import argparse
import json
import signal
from datetime import datetime

class SyncEventHandler(FileSystemEventHandler):
    """Maneja eventos de cambios en el sistema de archivos."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger("SyncEventHandler")
        self.ignored_dirs = config.get("ignored_dirs", [
            ".git", "node_modules", "__pycache__", ".venv", ".env",
            ".vscode", "dist", "build", "logs", "spec", "AURA-Desktop"
        ])
        self.excluded_extensions = config.get("excluded_extensions", [
            ".log", ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".min.js", ".min.css"
        ])

    def should_ignore(self, file_path: str) -> bool:
        """Determina si un archivo o directorio debe ser ignorado."""
        try:
            # Ignorar directorios
            for ignored_dir in self.ignored_dirs:
                if ignored_dir in file_path:
                    return True

            # Ignorar extensiones
            if os.path.splitext(file_path)[1] in self.excluded_extensions:
                return True

            # Ignorar archivos ocultos
            if file_path.startswith('.'):
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error al verificar exclusión para {file_path}: {str(e)}")
            return True

    def is_valid_file(self, file_path: str) -> bool:
        """Verifica si el archivo es válido para sincronizar."""
        try:
            if not os.path.isfile(file_path):
                return False

            # Verificar que el archivo no sea un enlace simbólico
            if os.path.islink(file_path):
                return False

            # Verificar que el archivo tenga contenido
            if os.path.getsize(file_path) == 0:
                self.logger.debug(f"Archivo vacío ignorado: {file_path}")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Error al verificar archivo {file_path}: {str(e)}")
            return False

    def on_modified(self, event):
        """Evento llamado cuando un archivo es modificado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path) and self.is_valid_file(file_path):
                self.logger.info(f"Cambio detectado en: {file_path}")
                self.trigger_sync(file_path)

    def on_created(self, event):
        """Evento llamado cuando un archivo es creado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path) and self.is_valid_file(file_path):
                self.logger.info(f"Archivo creado: {file_path}")
                self.trigger_sync(file_path)

    def on_deleted(self, event):
        """Evento llamado cuando un archivo es eliminado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path):
                self.logger.info(f"Archivo eliminado: {file_path}")
                self.trigger_sync(file_path, is_deleted=True)

    def trigger_sync(self, file_path: str, is_deleted: bool = False):
        """Dispara la sincronización para un archivo específico."""
        try:
            # Obtener la ruta relativa desde el directorio de desarrollo
            relative_path = os.path.relpath(file_path, self.config["local_dev_dir"])

            # Determinar el comando rsync adecuado
            if is_deleted:
                command = self._build_delete_command(relative_path)
            else:
                command = self._build_sync_command(relative_path)

            # Ejecutar el comando
            self.logger.debug(f"Ejecutando comando: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False
            )

            # Registrar el resultado
            if result.returncode == 0:
                self.logger.info(f"Sincronización exitosa para: {relative_path}")
            else:
                self.logger.error(f"Error al sincronizar {relative_path}: {result.stderr}")

        except Exception as e:
            self.logger.error(f"Error al sincronizar {file_path}: {str(e)}")

    def _build_sync_command(self, relative_path: str) -> List[str]:
        """Construye el comando rsync para sincronizar un archivo."""
        local_path = os.path.join(self.config["local_dev_dir"], relative_path)
        remote_path = os.path.join(self.config["remote_app_dir"], relative_path)

        # Crear directorios remotos si no existen
        mkdir_command = [
            "ssh", "-p", str(self.config["ssh_port"]),
            f"{self.config['ssh_user']}@{self.config['ssh_host']}",
            f"mkdir -p {os.path.dirname(remote_path)}"
        ]

        # Comando rsync principal
        rsync_command = [
            "rsync",
            "-avz",
            "--delete",  # Eliminar archivos en el destino que ya no existan en el origen
            "--exclude='*.log'",
            "--exclude='*.pyc'",
            "--exclude='*.pyo'",
            "--exclude='*.pyd'",
            f"{local_path}/",
            f"{self.config['ssh_user']}@{self.config['ssh_host']}:{remote_path}"
        ]

        return mkdir_command + rsync_command

    def _build_delete_command(self, relative_path: str) -> List[str]:
        """Construye el comando para eliminar un archivo en el dispositivo remoto."""
        remote_path = os.path.join(self.config["remote_app_dir"], relative_path)
        return [
            "ssh", "-p", str(self.config["ssh_port"]),
            f"{self.config['ssh_user']}@{self.config['ssh_host']}",
            f"rm -f {remote_path}"
        ]

class LiveSyncService:
    """Servicio principal de sincronización en tiempo real."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.event_handler = SyncEventHandler(config)
        self.observer = None
        self.running = False
        self.last_sync_time = 0
        self.sync_interval = config.get("sync_interval", 60)  # segundos

    def _setup_logging(self):
        """Configura el logging para el servicio de sincronización."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sync_service.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("LiveSyncService")
        logger.setLevel(logging.INFO)
        return logger

    def _validate_config(self):
        """Valida la configuración del servicio."""
        required_keys = [
            "local_dev_dir", "remote_app_dir",
            "ssh_host", "ssh_port", "ssh_user"
        ]

        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Configuración faltante: {key}")

        # Verificar que los directorios locales existan
        if not os.path.exists(self.config["local_dev_dir"]):
            raise ValueError(f"Directorio local no existe: {self.config['local_dev_dir']}")

    def _setup_observer(self):
        """Configura el observador de watchdog."""
        try:
            self.observer = Observer()
            for watch_dir in self.config.get("watch_dirs", [self.config["local_dev_dir"]]):
                self.observer.schedule(
                    self.event_handler,
                    watch_dir,
                    recursive=True
                )
            self.logger.info(f"Observando directorios: {self.config.get('watch_dirs', [self.config['local_dev_dir']])}")
        except Exception as e:
            self.logger.error(f"Error al configurar observador: {str(e)}")
            raise

    def _test_ssh_connection(self):
        """Prueba la conexión SSH antes de iniciar el servicio."""
        try:
            command = [
                "ssh", "-p", str(self.config["ssh_port"]),
                f"{self.config['ssh_user']}@{self.config['ssh_host']}",
                "echo 'SSH connection test successful'"
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.info("Conexión SSH verificada con éxito.")
                return True
            else:
                self.logger.error(f"Error en la conexión SSH: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error al probar conexión SSH: {str(e)}")
            return False

    def _initial_sync(self):
        """Realiza una sincronización inicial completa."""
        try:
            self.logger.info("Iniciando sincronización inicial...")
            start_time = time.time()

            # Usar rsync para sincronizar todos los directorios
            for watch_dir in self.config.get("watch_dirs", [self.config["local_dev_dir"]]):
                relative_dir = os.path.relpath(watch_dir, self.config["local_dev_dir"])
                remote_dir = os.path.join(self.config["remote_app_dir"], relative_dir)

                command = [
                    "rsync",
                    "-avz",
                    "--delete",
                    "--exclude='.git'",
                    "--exclude='node_modules'",
                    "--exclude='*.log'",
                    "--exclude='*.pyc'",
                    "--exclude='*.pyo'",
                    "--exclude='*.pyd'",
                    f"{watch_dir}/",
                    f"{self.config['ssh_user']}@{self.config['ssh_host']}:{remote_dir}"
                ]

                self.logger.debug(f"Ejecutando sincronización inicial: {' '.join(command)}")
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.logger.info(f"Sincronización inicial exitosa para: {relative_dir}")
                else:
                    self.logger.error(f"Error en sincronización inicial para {relative_dir}: {result.stderr}")

            end_time = time.time()
            self.logger.info(f"Sincronización inicial completada en {end_time - start_time:.2f} segundos.")
            self.last_sync_time = end_time
        except Exception as e:
            self.logger.error(f"Error en sincronización inicial: {str(e)}")

    def _periodic_sync_check(self):
        """Realiza una sincronización periódica para archivos que puedan no haber sido detectados."""
        current_time = time.time()
        if current_time - self.last_sync_time > self.sync_interval:
            self.logger.info(f"Realizando sincronización periódica (intervalo: {self.sync_interval} segundos)...")
            try:
                # Escanear todos los directorios observados
                for watch_dir in self.config.get("watch_dirs", [self.config["local_dev_dir"]]):
                    for root, _, files in os.walk(watch_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if not self.event_handler.should_ignore(file_path):
                                self.event_handler.trigger_sync(file_path)
                self.last_sync_time = current_time
            except Exception as e:
                self.logger.error(f"Error en sincronización periódica: {str(e)}")

    def start(self):
        """Inicia el servicio de sincronización."""
        try:
            self._validate_config()
            if not self._test_ssh_connection():
                raise ConnectionError("No se pudo establecer conexión SSH. Verificar configuración.")

            self._setup_observer()
            self._initial_sync()

            self.running = True
            self.logger.info("Servicio de sincronización en tiempo real iniciado.")

            # Iniciar el observador
            self.observer.start()

            # Bucle principal para sincronización periódica
            while self.running:
                self._periodic_sync_check()
                time.sleep(5)

        except KeyboardInterrupt:
            self.logger.info("Deteniendo servicio de sincronización...")
        except Exception as e:
            self.logger.error(f"Error en el servicio de sincronización: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """Detiene el servicio de sincronización."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            self.logger.info("Observador de watchdog detenido.")
        self.running = False

def load_config(config_file: str = "sync_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "sync_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para la sincronización."""
    return {
        "local_dev_dir": os.path.join(os.getcwd(), "AURA_Core"),
        "remote_app_dir": "/data/data/com.termux/files/home/AME_Core",
        "watch_dirs": [
            os.path.join(os.getcwd(), "AURA_Core"),
            os.path.join(os.getcwd(), "AME_Core")
        ],
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "ignored_dirs": [
            ".git", "node_modules", "__pycache__", ".venv", ".env",
            ".vscode", "dist", "build", "logs", "spec", "AURA-Desktop"
        ],
        "excluded_extensions": [
            ".log", ".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".min.js", ".min.css"
        ],
        "sync_interval": 60,
        "log_file": "sync_service.log"
    }

def main():
    """Punto de entrada principal del servicio de sincronización."""
    parser = argparse.ArgumentParser(description="Servicio de sincronización en tiempo real para AURA/AME.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="sync_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("Configuración por defecto guardada en sync_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        service = LiveSyncService(config)
        service.start()

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()