#!/usr/bin/env python3
"""
AURA Windows Task Scheduler - Configuración de tareas programadas para Windows
Usa win32com.client para interactuar con el Programador de Tareas de Windows
"""

import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
import win32com.client

# Configuración global
LOG_FILE = "windows_task_scheduler.log"
BACKUP_SCRIPT = "backup_system.py"
TASK_NAME = "AURA Weekly Backup"
TASK_DESCRIPTION = "Backup semanal automático del sistema AURA"
TASK_SCHEDULE = {
    "StartBoundary": "2026-01-01T00:00:00",  # Domingo a las 00:00
    "EndBoundary": "2027-01-01T00:00:00",  # Fecha de expiración (1 año después)
    "Repeat": {
        "Interval": "Weekly",
        "DaysInterval": 1,
        "WeeksInterval": 1,
        "MonthsInterval": 1,
        "MonthsOfYear": [],
        "DaysOfWeek": [1],  # Domingo (1 = Sunday)
        "DaysOfMonth": [],
        "StartDate": "2026-01-01",
    },
}

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)


class WindowsTaskScheduler:
    def __init__(self):
        self.task_service = win32com.client.Dispatch("Schedule.Service")
        self.task_service.Connect()
        self.script_dir = Path(__file__).parent
        self.backup_script_path = self.script_dir / BACKUP_SCRIPT
        self.task_exists = False

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

    def check_task_exists(self):
        """Verifica si la tarea programada ya existe"""
        try:
            tasks = self.task_service.GetFolder("\\").GetTasks(0)
            for task in tasks:
                if task.Name == TASK_NAME:
                    self.task_exists = True
                    return True
            return False
        except Exception as e:
            logging.error(f"Error verificando tarea existente: {str(e)}")
            return False

    def create_task(self):
        """Crea la tarea programada en el Programador de Tareas de Windows"""
        if not self.check_backup_script():
            return False

        try:
            # Verificar si ya existe la tarea
            if self.check_task_exists():
                logging.info("Tarea programada ya existe. Verificando...")
                return True

            # Crear la tarea
            task = self.task_service.NewTask(0)
            task.RegistrationInfo.Description = TASK_DESCRIPTION

            # Configurar el trigger (programación)
            trigger = task.Triggers.Create(1)  # 1 = Weekly trigger
            trigger.StartBoundary = TASK_SCHEDULE["StartBoundary"]
            trigger.EndBoundary = TASK_SCHEDULE["EndBoundary"]
            trigger.Repetition.Interval = TASK_SCHEDULE["Repeat"]["Interval"]
            trigger.Repetition.DaysInterval = TASK_SCHEDULE["Repeat"]["DaysInterval"]
            trigger.Repetition.WeeksInterval = TASK_SCHEDULE["Repeat"]["WeeksInterval"]
            trigger.Repetition.MonthsInterval = TASK_SCHEDULE["Repeat"][
                "MonthsInterval"
            ]
            trigger.Repetition.DaysOfWeek = TASK_SCHEDULE["Repeat"]["DaysOfWeek"]
            trigger.Repetition.StartDate = TASK_SCHEDULE["Repeat"]["StartDate"]

            # Configurar la acción (qué hacer)
            action = task.Actions.Create(0)  # 0 = Exec action
            action.Path = sys.executable
            action.Arguments = f'"{self.backup_script_path}" backup'

            # Configurar configuración adicional
            settings = task.Settings
            settings.Enabled = True
            settings.AllowStartIfOnBatteries = True
            settings.StartWhenAvailable = True
            settings.RunOnlyIfNetworkAvailable = True
            settings.StopIfGoingOnBatteries = False
            settings.DisallowStartIfOnBatteries = False
            settings.AllowHardTerminate = True
            settings.StartWhenAvailable = True
            settings.RunOnlyIfIdle = False
            settings.Priority = 4  # 4 = Normal

            # Registrar la tarea
            self.task_service.GetFolder("\\").RegisterTaskDefinition(
                TASK_NAME,
                task,
                6,  # 6 = Update existing task
                None,
                None,
                3,  # 3 = Run whether user is logged on or not
            )

            logging.info(f"Tarea programada creada con éxito: {TASK_NAME}")
            logging.info(f"Descripción: {TASK_DESCRIPTION}")
            logging.info(f"Programación: Domingo a las 00:00")
            logging.info(
                f'Comando: {sys.executable} "{self.backup_script_path}" backup'
            )
            return True

        except Exception as e:
            logging.error(f"Error creando tarea en Windows: {str(e)}")
            return False

    def verify_task(self):
        """Verifica que la tarea programada esté configurada correctamente"""
        try:
            tasks = self.task_service.GetFolder("\\").GetTasks(0)
            for task in tasks:
                if task.Name == TASK_NAME:
                    self.task_exists = True
                    logging.info(f"Tarea programada verificada: {TASK_NAME}")
                    logging.info(f"Descripción: {task.RegistrationInfo.Description}")
                    logging.info(
                        f"Estado: {'Habilitada' if task.Settings.Enabled else 'Deshabilitada'}"
                    )

                    # Verificar triggers
                    triggers = task.Triggers
                    if triggers.Count > 0:
                        trigger = triggers[0]
                        logging.info(
                            f"Programación: {trigger.StartBoundary} (cada {trigger.Repetition.Interval})"
                        )

                    # Verificar acciones
                    actions = task.Actions
                    if actions.Count > 0:
                        action = actions[0]
                        logging.info(f"Comando: {action.Path} {action.Arguments}")

                    return True

            logging.warning(f"Tarea programada no encontrada: {TASK_NAME}")
            return False

        except Exception as e:
            logging.error(f"Error verificando tarea en Windows: {str(e)}")
            return False

    def remove_task(self):
        """Elimina la tarea programada"""
        try:
            if not self.check_task_exists():
                logging.warning(f"No se encontró la tarea para eliminar: {TASK_NAME}")
                return True

            self.task_service.GetFolder("\\").DeleteTask(TASK_NAME, 0)
            logging.info(f"Tarea programada eliminada con éxito: {TASK_NAME}")
            return True

        except Exception as e:
            logging.error(f"Error eliminando tarea en Windows: {str(e)}")
            return False

    def get_task_status(self):
        """Obtiene el estado actual de la tarea programada"""
        status = {
            "task_name": TASK_NAME,
            "task_exists": self.task_exists,
            "backup_script": str(self.backup_script_path),
            "backup_script_exists": self.backup_script_path.exists(),
            "backup_script_executable": os.access(self.backup_script_path, os.X_OK),
            "last_verification": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schedule": "Domingo a las 00:00",
            "description": TASK_DESCRIPTION,
        }

        try:
            tasks = self.task_service.GetFolder("\\").GetTasks(0)
            for task in tasks:
                if task.Name == TASK_NAME:
                    status["enabled"] = task.Settings.Enabled
                    status["next_run_time"] = task.NextRunTime
                    status["last_run_time"] = task.LastRunTime
                    status["last_result"] = task.LastTaskResult
                    status["task_exists"] = True
                    break
        except Exception as e:
            logging.error(f"Error obteniendo estado de la tarea: {str(e)}")

        return status


def main():
    """Función principal para configurar la tarea en Windows"""
    task_scheduler = WindowsTaskScheduler()

    # Verificar el script de backup
    if not task_scheduler.check_backup_script():
        logging.error("No se puede continuar sin el script de backup")
        return False

    # Crear la tarea programada
    if task_scheduler.create_task():
        logging.info("Tarea programada configurada con éxito")

        # Verificar la configuración
        if task_scheduler.verify_task():
            status = task_scheduler.get_task_status()
            logging.info("Estado de la configuración:")
            logging.info(json.dumps(status, indent=2))
            return True
        else:
            logging.warning("La tarea programada no pudo ser verificada")
            return False
    else:
        logging.error("No se pudo configurar la tarea programada")
        return False


def verify_task():
    """Verifica el estado actual de la tarea programada"""
    task_scheduler = WindowsTaskScheduler()
    status = task_scheduler.get_task_status()

    print("Estado de la tarea programada en Windows:")
    print("=" * 50)
    print(f"Nombre de la tarea: {status['task_name']}")
    print(f"Tarea existe: {'✅ Sí' if status['task_exists'] else '❌ No'}")
    print(f"Script de backup: {status['backup_script']}")
    print(f"Script existe: {'✅ Sí' if status['backup_script_exists'] else '❌ No'}")
    print(
        f"Script ejecutable: {'✅ Sí' if status['backup_script_executable'] else '❌ No'}"
    )

    if status["task_exists"]:
        print(
            f"Estado: {'✅ Habilitada' if status.get('enabled', False) else '❌ Deshabilitada'}"
        )
        print(f"Programación: {status['schedule']}")
        print(f"Descripción: {status['description']}")

        if "next_run_time" in status and status["next_run_time"]:
            print(f"Próxima ejecución: {status['next_run_time']}")
        if "last_run_time" in status and status["last_run_time"]:
            print(f"Última ejecución: {status['last_run_time']}")
        if "last_result" in status and status["last_result"]:
            print(f"Resultado de la última ejecución: {status['last_result']}")

    print(f"Última verificación: {status['last_verification']}")
    print("=" * 50)

    return status


def remove_task():
    """Elimina la tarea programada"""
    task_scheduler = WindowsTaskScheduler()
    if task_scheduler.remove_task():
        logging.info("Tarea programada eliminada con éxito")
        return True
    else:
        logging.error("No se pudo eliminar la tarea programada")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_task()
    elif len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_task()
    else:
        # Configurar por defecto
        success = main()
        sys.exit(0 if success else 1)
