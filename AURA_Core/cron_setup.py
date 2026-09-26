#!/usr/bin/env python3
"""
AURA Cron Setup - Configuración de tareas programadas para el sistema
Configura tareas automáticas usando el cron de Windows o el sistema operativo
"""

import os
import sys
import platform
import subprocess
from pathlib import Path
import logging
import json
from datetime import datetime

# Configuración global
LOG_FILE = "cron_setup.log"
BACKUP_SCRIPT = "backup_system.py"
CRON_JOB_NAME = "aura_weekly_backup"
CRON_SCHEDULE = "0 0 * * 0"  # Cada domingo a las 00:00 (00:00 del domingo)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)


class CronSetup:
    def __init__(self):
        self.system = platform.system().lower()
        self.home_dir = Path.home()
        self.script_dir = Path(__file__).parent
        self.backup_script_path = self.script_dir / BACKUP_SCRIPT
        self.cron_job_configured = False

    def check_backup_script(self):
        """Verifica que el script de backup exista y sea ejecutable"""
        if not self.backup_script_path.exists():
            logging.error(f"Script de backup no encontrado: {self.backup_script_path}")
            return False

        if not os.access(self.backup_script_path, os.X_OK):
            logging.warning(
                f"Script de backup no es ejecutable: {self.backup_script_path}"
            )
            return False

        return True

    def configure_cron_job(self):
        """Configura la tarea programada para el backup semanal"""
        if not self.check_backup_script():
            return False

        try:
            if self.system == "windows":
                return self._configure_windows_task_scheduler()
            elif self.system == "linux":
                return self._configure_linux_cron()
            elif self.system == "darwin":  # macOS
                return self._configure_macos_launchd()
            else:
                logging.error(f"Sistema operativo no soportado: {self.system}")
                return False
        except Exception as e:
            logging.error(f"Error configurando tarea programada: {str(e)}")
            return False

    def _configure_windows_task_scheduler(self):
        """Configura la tarea en el Programador de Tareas de Windows"""
        try:
            # Verificar si ya existe la tarea
            task_exists = self._check_task_exists()

            if task_exists:
                logging.info("Tarea programada ya existe. Verificando...")
                return True

            # Crear la tarea
            command = [
                "schtasks",
                "/create",
                f"/tn {CRON_JOB_NAME}",
                f'/tr "{self.backup_script_path}" backup',
                f"/sc weekly",
                "/d SUN",
                "/st 00:00",
                "/ru System",
                "/f",
            ]

            result = subprocess.run(command, check=True, capture_output=True, text=True)

            logging.info(f"Tarea programada creada con éxito: {CRON_JOB_NAME}")
            logging.info(f"Comando: {' '.join(command)}")
            logging.info(f"Salida: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Error creando tarea en Windows: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            return False

    def _check_task_exists(self):
        """Verifica si la tarea programada ya existe"""
        try:
            result = subprocess.run(
                ["schtasks", "/query", f"/tn {CRON_JOB_NAME}", "/fo", "csv"],
                capture_output=True,
                text=True,
            )

            return CRON_JOB_NAME in result.stdout
        except Exception as e:
            logging.error(f"Error verificando tarea existente: {str(e)}")
            return False

    def _configure_linux_cron(self):
        """Configura la tarea en el cron de Linux"""
        try:
            # Verificar si ya existe la entrada en crontab
            crontab_content = self._get_crontab_content()
            if self._cron_entry_exists(crontab_content):
                logging.info("Entrada de cron ya existe. Verificando...")
                return True

            # Obtener la ruta absoluta del script
            abs_script_path = str(self.backup_script_path.resolve())

            # Crear la entrada de cron
            cron_entry = f"{CRON_SCHEDULE} {abs_script_path} backup >> {self.script_dir}/backup_cron.log 2>&1\n"

            # Añadir la entrada al crontab
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)

            current_crontab = result.stdout
            updated_crontab = current_crontab + cron_entry

            with open("/tmp/crontab_new", "w") as f:
                f.write(updated_crontab)

            subprocess.run(["crontab", "/tmp/crontab_new"], check=True)

            os.remove("/tmp/crontab_new")
            logging.info(f"Entrada de cron añadida con éxito: {cron_entry.strip()}")
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Error configurando cron en Linux: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            return False

    def _get_crontab_content(self):
        """Obtiene el contenido actual de crontab"""
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            return result.stdout
        except subprocess.CalledProcessError:
            return ""

    def _cron_entry_exists(self, crontab_content):
        """Verifica si la entrada de cron ya existe"""
        return CRON_SCHEDULE in crontab_content and BACKUP_SCRIPT in crontab_content

    def _configure_macos_launchd(self):
        """Configura la tarea en launchd de macOS"""
        try:
            # Verificar si ya existe el servicio
            plist_path = self.home_dir / "Library/LaunchAgents/com.aura.backup.plist"
            if plist_path.exists():
                logging.info("Servicio launchd ya existe. Verificando...")
                return True

            # Crear el archivo de configuración
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aura.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self.backup_script_path}</string>
        <string>backup</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer> <!-- Domingo -->
        <key>Hour</key>
        <integer>0</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{self.script_dir}/backup_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>{self.script_dir}/backup_launchd_error.log</string>
</dict>
</plist>
"""

            with open(plist_path, "w") as f:
                f.write(plist_content)

            # Cargar el servicio
            subprocess.run(["launchctl", "load", str(plist_path)], check=True)

            logging.info(f"Servicio launchd creado con éxito: {plist_path}")
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Error configurando launchd en macOS: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            return False

    def verify_cron_job(self):
        """Verifica que la tarea programada esté configurada correctamente"""
        try:
            if self.system == "windows":
                return self._verify_windows_task()
            elif self.system == "linux":
                return self._verify_linux_cron()
            elif self.system == "darwin":
                return self._verify_macos_launchd()
            else:
                logging.error(
                    f"Sistema operativo no soportado para verificación: {self.system}"
                )
                return False
        except Exception as e:
            logging.error(f"Error verificando tarea programada: {str(e)}")
            return False

    def _verify_windows_task(self):
        """Verifica la tarea en Windows"""
        try:
            result = subprocess.run(
                ["schtasks", "/query", f"/tn {CRON_JOB_NAME}", "/fo", "csv"],
                capture_output=True,
                text=True,
            )

            if CRON_JOB_NAME in result.stdout:
                self.cron_job_configured = True
                logging.info(f"Tarea programada verificada: {CRON_JOB_NAME}")
                return True
            else:
                logging.warning(f"Tarea programada no encontrada: {CRON_JOB_NAME}")
                return False
        except Exception as e:
            logging.error(f"Error verificando tarea en Windows: {str(e)}")
            return False

    def _verify_linux_cron(self):
        """Verifica la entrada de cron en Linux"""
        try:
            crontab_content = self._get_crontab_content()
            if self._cron_entry_exists(crontab_content):
                self.cron_job_configured = True
                logging.info("Entrada de cron verificada con éxito")
                return True
            else:
                logging.warning("Entrada de cron no encontrada")
                return False
        except Exception as e:
            logging.error(f"Error verificando cron en Linux: {str(e)}")
            return False

    def _verify_macos_launchd(self):
        """Verifica el servicio launchd en macOS"""
        try:
            plist_path = self.home_dir / "Library/LaunchAgents/com.aura.backup.plist"
            if plist_path.exists():
                self.cron_job_configured = True
                logging.info("Servicio launchd verificado con éxito")
                return True
            else:
                logging.warning("Servicio launchd no encontrado")
                return False
        except Exception as e:
            logging.error(f"Error verificando launchd en macOS: {str(e)}")
            return False

    def remove_cron_job(self):
        """Elimina la tarea programada"""
        try:
            if self.system == "windows":
                return self._remove_windows_task()
            elif self.system == "linux":
                return self._remove_linux_cron()
            elif self.system == "darwin":
                return self._remove_macos_launchd()
            else:
                logging.error(
                    f"Sistema operativo no soportado para eliminación: {self.system}"
                )
                return False
        except Exception as e:
            logging.error(f"Error eliminando tarea programada: {str(e)}")
            return False

    def _remove_windows_task(self):
        """Elimina la tarea en Windows"""
        try:
            result = subprocess.run(
                ["schtasks", "/delete", f"/tn {CRON_JOB_NAME}", "/f"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logging.info(f"Tarea programada eliminada con éxito: {CRON_JOB_NAME}")
                return True
            else:
                logging.warning(f"No se pudo eliminar la tarea: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Error eliminando tarea en Windows: {str(e)}")
            return False

    def _remove_linux_cron(self):
        """Elimina la entrada de cron en Linux"""
        try:
            crontab_content = self._get_crontab_content()
            if not self._cron_entry_exists(crontab_content):
                logging.warning("No se encontró entrada de cron para eliminar")
                return True

            # Crear un nuevo crontab sin la entrada
            lines = crontab_content.split("\n")
            new_crontab = "\n".join(
                [line for line in lines if not self._line_matches_cron_entry(line)]
            )

            if new_crontab.strip():
                with open("/tmp/crontab_new", "w") as f:
                    f.write(new_crontab)

                subprocess.run(["crontab", "/tmp/crontab_new"], check=True)

                os.remove("/tmp/crontab_new")
                logging.info("Entrada de cron eliminada con éxito")
                return True
            else:
                # Si el crontab queda vacío, eliminarlo completamente
                subprocess.run(["crontab", "-r"], check=True)
                logging.info("Crontab vacío eliminado")
                return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Error eliminando entrada de cron: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            return False

    def _line_matches_cron_entry(self, line):
        """Verifica si una línea del crontab coincide con nuestra entrada"""
        return CRON_SCHEDULE in line and BACKUP_SCRIPT in line and "backup" in line

    def _remove_macos_launchd(self):
        """Elimina el servicio launchd en macOS"""
        try:
            plist_path = self.home_dir / "Library/LaunchAgents/com.aura.backup.plist"
            if not plist_path.exists():
                logging.warning("Servicio launchd no encontrado para eliminar")
                return True

            # Descarregar el servicio
            subprocess.run(["launchctl", "unload", str(plist_path)], check=True)

            # Eliminar el archivo
            plist_path.unlink()
            logging.info("Servicio launchd eliminado con éxito")
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Error eliminando servicio launchd: {e.stderr}")
            return False
        except Exception as e:
            logging.error(f"Error inesperado: {str(e)}")
            return False

    def get_cron_status(self):
        """Obtiene el estado actual de la configuración de cron"""
        status = {
            "system": self.system,
            "backup_script": str(self.backup_script_path),
            "backup_script_exists": self.backup_script_path.exists(),
            "backup_script_executable": os.access(self.backup_script_path, os.X_OK),
            "cron_job_configured": self.cron_job_configured,
            "last_verification": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schedule": CRON_SCHEDULE,
            "job_name": CRON_JOB_NAME,
        }

        if self.system == "windows":
            status["task_exists"] = self._check_task_exists()
        elif self.system == "linux":
            crontab_content = self._get_crontab_content()
            status["cron_entry_exists"] = self._cron_entry_exists(crontab_content)
        elif self.system == "darwin":
            plist_path = self.home_dir / "Library/LaunchAgents/com.aura.backup.plist"
            status["launchd_service_exists"] = plist_path.exists()

        return status


def main():
    """Función principal para configurar el cron"""
    cron_setup = CronSetup()

    # Verificar el script de backup
    if not cron_setup.check_backup_script():
        logging.error("No se puede continuar sin el script de backup")
        return False

    # Configurar la tarea programada
    if cron_setup.configure_cron_job():
        logging.info("Tarea programada configurada con éxito")

        # Verificar la configuración
        if cron_setup.verify_cron_job():
            status = cron_setup.get_cron_status()
            logging.info("Estado de la configuración:")
            logging.info(json.dumps(status, indent=2))
            return True
        else:
            logging.warning("La tarea programada no pudo ser verificada")
            return False
    else:
        logging.error("No se pudo configurar la tarea programada")
        return False


def verify_cron():
    """Verifica el estado actual de la configuración de cron"""
    cron_setup = CronSetup()
    status = cron_setup.get_cron_status()

    print("Estado de la configuración de cron:")
    print("=" * 50)
    print(f"Sistema operativo: {status['system']}")
    print(f"Script de backup: {status['backup_script']}")
    print(f"Script existe: {'✅ Sí' if status['backup_script_exists'] else '❌ No'}")
    print(
        f"Script ejecutable: {'✅ Sí' if status['backup_script_executable'] else '❌ No'}"
    )
    print(
        f"Tarea programada configurada: {'✅ Sí' if status['cron_job_configured'] else '❌ No'}"
    )

    if status["system"] == "windows":
        print(
            f"Tarea existe en Windows: {'✅ Sí' if status.get('task_exists', False) else '❌ No'}"
        )
    elif status["system"] == "linux":
        print(
            f"Entrada de cron existe: {'✅ Sí' if status.get('cron_entry_exists', False) else '❌ No'}"
        )
    elif status["system"] == "darwin":
        print(
            f"Servicio launchd existe: {'✅ Sí' if status.get('launchd_service_exists', False) else '❌ No'}"
        )

    print(f"Programación: {status['schedule']} (cada {status['job_name']})")
    print(f"Última verificación: {status['last_verification']}")
    print("=" * 50)

    return status


def remove_cron_job():
    """Elimina la tarea programada"""
    cron_setup = CronSetup()
    if cron_setup.remove_cron_job():
        logging.info("Tarea programada eliminada con éxito")
        return True
    else:
        logging.error("No se pudo eliminar la tarea programada")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_cron()
    elif len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_cron_job()
    else:
        # Configurar por defecto
        success = main()
        sys.exit(0 if success else 1)
