#!/usr/bin/env python3
"""
AURA Backup System - Script para crear snapshots del sistema
Crea copias comprimidas de AME_Core/, Automation_Bots/ y la base de datos local
"""

import os
import sys
import shutil
import tarfile
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Configuración global
BACKUP_DIR = "backups"
MAX_BACKUPS = 4  # Número máximo de backups guardados
LOG_FILE = "backup_system.log"
DB_FILES = ["watchlist.json", "alerts.json", "memory_buffer.json"]

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)


class BackupSystem:
    def __init__(self):
        self.backup_dir = Path(BACKUP_DIR)
        self.current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_name = f"aura_backup_{self.current_time}"
        self.backup_path = self.backup_dir / self.backup_name
        self.success = False
        self.error_message = None

    def create_backup(self):
        """Crea un backup completo del sistema"""
        try:
            # Crear directorio de backups si no existe
            self.backup_dir.mkdir(exist_ok=True)
            self.backup_path.mkdir(parents=True, exist_ok=True)

            # Crear archivo tar.gz
            with tarfile.open(self.backup_path.with_suffix(".tar.gz"), "w:gz") as tar:
                # Añadir directorios principales
                self._add_directory_to_tar(tar, "AME_Core")
                self._add_directory_to_tar(tar, "Automation_Bots")

                # Añadir archivos de base de datos
                for db_file in DB_FILES:
                    db_path = Path(db_file)
                    if db_path.exists():
                        tar.add(db_path, arcname=db_path.name)

                # Añadir metadata del backup
                metadata = {
                    "timestamp": self.current_time,
                    "system": "AURA",
                    "version": "1.0",
                    "components": ["AME_Core", "Automation_Bots"] + DB_FILES,
                }
                metadata_path = self.backup_path / "metadata.json"
                with open(metadata_path, "w") as f:
                    json.dump(metadata, f, indent=2)

                tar.add(metadata_path, arcname="metadata.json")

            # Crear archivo de índice
            self._create_index_file()

            self.success = True
            logging.info(f"Backup creado exitosamente: {self.backup_path.name}")
            return True

        except Exception as e:
            self.error_message = str(e)
            logging.error(f"Error creando backup: {str(e)}")
            return False

    def _add_directory_to_tar(self, tar, directory_name):
        """Añade un directorio completo al archivo tar"""
        dir_path = Path(directory_name)
        if not dir_path.exists():
            logging.warning(f"Directorio no encontrado: {directory_name}")
            return

        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(dir_path).as_posix()
                tar.add(file_path, arcname=arcname)

    def _create_index_file(self):
        """Crea un archivo de índice para el backup"""
        index_path = self.backup_path / "index.txt"
        with open(index_path, "w") as f:
            f.write(f"Backup de AURA - {self.current_time}\n")
            f.write("=================================\n\n")

            # Listar archivos en el backup
            with tarfile.open(self.backup_path.with_suffix(".tar.gz"), "r:gz") as tar:
                for member in tar.getmembers():
                    f.write(f"{member.name}\n")

            f.write(f"\nBackup creado por: {os.path.basename(__file__)}")
            f.write(f"\nRuta: {self.backup_path}\n")

    def cleanup_old_backups(self):
        """Elimina backups antiguos para mantener el límite máximo"""
        try:
            if not self.backup_dir.exists():
                return

            # Obtener todos los backups ordenados por fecha (más antiguo primero)
            backups = sorted(
                [f for f in self.backup_dir.glob("aura_backup_*") if f.is_dir()],
                key=lambda x: x.name,
            )

            # Eliminar backups que excedan el límite
            while len(backups) > MAX_BACKUPS:
                old_backup = backups.pop(0)
                old_tar = old_backup.with_suffix(".tar.gz")
                old_index = old_backup / "index.txt"
                old_metadata = old_backup / "metadata.json"

                # Eliminar todos los archivos del backup
                if old_tar.exists():
                    old_tar.unlink()
                if old_index.exists():
                    old_index.unlink()
                if old_metadata.exists():
                    old_metadata.unlink()

                # Eliminar el directorio vacío
                old_backup.rmdir()

                logging.info(f"Eliminado backup antiguo: {old_backup.name}")

        except Exception as e:
            logging.error(f"Error limpiando backups antiguos: {str(e)}")

    def verify_backup(self, backup_path=None):
        """Verifica la integridad de un backup"""
        if not backup_path:
            backup_path = self.backup_path

        if not backup_path.exists():
            return False, "Backup no encontrado"

        try:
            # Verificar que el archivo tar exista y sea válido
            tar_path = backup_path.with_suffix(".tar.gz")
            if not tar_path.exists():
                return False, "Archivo tar no encontrado"

            with tarfile.open(tar_path, "r:gz") as tar:
                # Verificar que tenga al menos algunos archivos
                if len(tar.getmembers()) < 10:  # Mínimo 10 archivos
                    return False, "Backup parece estar vacío o incompleto"

                # Verificar que tenga metadata.json
                metadata = None
                for member in tar.getmembers():
                    if member.name == "metadata.json":
                        metadata = member
                        break

                if not metadata:
                    return False, "Metadata no encontrada en el backup"

                # Verificar que el metadata sea válido
                with tarfile.open(tar_path, "r:gz") as tar:
                    with tar.extractfile(metadata) as f:
                        try:
                            metadata_content = json.load(f)
                            if not metadata_content.get("timestamp"):
                                return False, "Metadata inválido (sin timestamp)"
                        except json.JSONDecodeError:
                            return False, "Metadata corrupto (no es JSON válido)"

            return True, "Backup verificado correctamente"

        except Exception as e:
            return False, f"Error verificando backup: {str(e)}"

    def restore_system(self, backup_path=None):
        """Restaura el sistema desde un backup"""
        if not backup_path:
            backup_path = self.backup_path

        if not backup_path.exists():
            return False, "Backup no encontrado"

        try:
            # Verificar el backup antes de restaurar
            is_valid, message = self.verify_backup(backup_path)
            if not is_valid:
                return False, f"Backup inválido: {message}"

            # Extraer el contenido del backup (validando rutas para evitar path traversal)
            tar_path = backup_path.with_suffix(".tar.gz")
            dest = Path(".").resolve()
            with tarfile.open(tar_path, "r:gz") as tar:
                for member in tar.getmembers():
                    target = (dest / member.name).resolve()
                    if dest != target and dest not in target.parents:
                        raise ValueError(f"Ruta insegura en el backup: {member.name}")
                tar.extractall(path=str(dest))

            logging.info(f"Sistema restaurado desde: {backup_path.name}")
            return True, "Restauración completada exitosamente"

        except Exception as e:
            self.error_message = str(e)
            logging.error(f"Error restaurando sistema: {str(e)}")
            return False, f"Error en la restauración: {str(e)}"

    def get_latest_backup(self):
        """Obtiene la ruta del último backup exitoso"""
        if not self.backup_dir.exists():
            return None

        # Obtener todos los backups ordenados por fecha (más reciente primero)
        backups = sorted(
            [f for f in self.backup_dir.glob("aura_backup_*") if f.is_dir()],
            key=lambda x: x.name,
            reverse=True,
        )

        if not backups:
            return None

        # Verificar cada backup hasta encontrar uno válido
        for backup in backups:
            is_valid, message = self.verify_backup(backup)
            if is_valid:
                return backup

        return None

    def list_backups(self):
        """Lista todos los backups disponibles con información básica"""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for backup_dir in self.backup_dir.glob("aura_backup_*"):
            if backup_dir.is_dir():
                try:
                    # Obtener metadata
                    tar_path = backup_dir.with_suffix(".tar.gz")
                    with tarfile.open(tar_path, "r:gz") as tar:
                        for member in tar.getmembers():
                            if member.name == "metadata.json":
                                with tar.extractfile(member) as f:
                                    metadata = json.load(f)
                                    break
                        else:
                            metadata = {}

                    # Verificar si el backup es válido
                    is_valid, _ = self.verify_backup(backup_dir)

                    backups.append(
                        {
                            "name": backup_dir.name,
                            "path": str(backup_dir),
                            "timestamp": metadata.get("timestamp", "desconocido"),
                            "valid": is_valid,
                            "size": (
                                self._get_backup_size(tar_path)
                                if tar_path.exists()
                                else "desconocido"
                            ),
                        }
                    )

                except Exception as e:
                    logging.error(
                        f"Error procesando backup {backup_dir.name}: {str(e)}"
                    )
                    backups.append(
                        {
                            "name": backup_dir.name,
                            "path": str(backup_dir),
                            "timestamp": "error",
                            "valid": False,
                            "size": "error",
                        }
                    )

        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

    def _get_backup_size(self, file_path):
        """Obtiene el tamaño de un archivo en formato legible"""
        if not file_path.exists():
            return "0 bytes"

        size_bytes = file_path.stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"


def main():
    """Función principal para ejecutar el backup"""
    backup_system = BackupSystem()

    # Crear backup
    if backup_system.create_backup():
        # Limpiar backups antiguos
        backup_system.cleanup_old_backups()

        # Obtener información del último backup
        latest_backup = backup_system.get_latest_backup()
        if latest_backup:
            logging.info(f"Último backup creado: {latest_backup.name}")
            logging.info(f"Ruta: {latest_backup}")
        else:
            logging.warning(
                "No se encontró ningún backup válido después de la creación"
            )

        return True
    else:
        logging.error(f"Backup fallido: {backup_system.error_message}")
        return False


def restore_from_latest():
    """Restaura el sistema desde el último backup válido"""
    backup_system = BackupSystem()
    latest_backup = backup_system.get_latest_backup()

    if not latest_backup:
        logging.error("No se encontró ningún backup válido")
        return False, "No hay backups válidos disponibles"

    success, message = backup_system.restore_system(latest_backup)
    if success:
        logging.info(f"Restauración exitosa desde: {latest_backup.name}")
    else:
        logging.error(f"Restauración fallida: {message}")

    return success, message


def list_all_backups():
    """Lista todos los backups disponibles"""
    backup_system = BackupSystem()
    backups = backup_system.list_backups()

    print("Lista de backups disponibles:")
    print("=" * 50)
    for backup in backups:
        status = "✅ Válido" if backup["valid"] else "❌ Inválido"
        print(f"{backup['name']} ({backup['timestamp']}) - {status} - {backup['size']}")

    print("=" * 50)
    print(f"Total: {len(backups)} backups")

    return backups


if __name__ == "__main__":
    # Ejecutar backup si se ejecuta directamente
    if len(sys.argv) > 1 and sys.argv[1] == "backup":
        success = main()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "restore":
        success, message = restore_from_latest()
        print(message)
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        list_all_backups()
    else:
        # Ejecutar backup por defecto
        main()
