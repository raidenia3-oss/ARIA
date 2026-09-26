#!/usr/bin/env python3
"""
AURA Live Reload - Sistema de recarga automática para Railway
Monitorea cambios en AME_Core/ y reinicia el servidor cuando se detectan modificaciones
"""

import os
import sys
import time
import subprocess
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_reload.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AURALiveReload')

class AURAReloadHandler(FileSystemEventHandler):
    """Maneja eventos de cambios en el sistema de archivos"""

    def __init__(self, server_process):
        self.server_process = server_process
        self.last_modified = 0
        self.cooldown = 5  # Segundos de cooldown para evitar reinicios múltiples

    def on_modified(self, event):
        """Evento llamado cuando un archivo es modificado"""
        if not event.is_directory and event.src_path.endswith('.py'):
            current_time = time.time()
            if current_time - self.last_modified > self.cooldown:
                self.last_modified = current_time
                logger.info(f"🔄 Cambio detectado en: {event.src_path}")
                self.trigger_reload()

    def trigger_reload(self):
        """Detona el reinicio del servidor"""
        logger.info("🚀 Reiniciando servidor debido a cambios en el código...")

        # Verificar si el proceso del servidor está activo
        if self.server_process and self.server_process.poll() is None:
            logger.info("🛑 Deteniendo proceso actual...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Proceso no respondió al término. Matando forzosamente...")
                self.server_process.kill()
            except Exception as e:
                logger.error(f"❌ Error al detener proceso: {str(e)}")

        # Iniciar nuevo proceso del servidor
        logger.info("🚀 Iniciando nuevo proceso del servidor...")
        try:
            # Cambiar al directorio correcto y ejecutar el servidor
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            self.server_process = subprocess.Popen(
                [sys.executable, "AME_Core/AME_Core/servidor_ame.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info("✅ Servidor reiniciado correctamente")
        except Exception as e:
            logger.error(f"❌ Error al reiniciar servidor: {str(e)}")

def start_server():
    """Inicia el servidor principal"""
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        logger.info("🚀 Iniciando servidor principal...")
        return subprocess.Popen(
            [sys.executable, "AME_Core/AME_Core/servidor_ame.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except Exception as e:
        logger.error(f"❌ Error al iniciar servidor: {str(e)}")
        return None

def monitor_directory(directory, server_process):
    """Monitorea un directorio específico para cambios"""
    event_handler = AURAReloadHandler(server_process)
    observer = Observer()
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()

    logger.info(f"👀 Monitoreando directorio: {directory}")
    logger.info("🔄 Presiona Ctrl+C para detener el sistema de monitoreo")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("🛑 Deteniendo monitoreo...")
    observer.join()

def main():
    """Punto de entrada principal"""
    logger.info("🚀 Iniciando AURA Live Reload System")

    # Iniciar el servidor principal
    server_process = start_server()
    if not server_process:
        logger.error("❌ No se pudo iniciar el servidor principal")
        return

    # Configurar el directorio a monitorear
    target_directory = Path(__file__).parent / "AME_Core"
    if not target_directory.exists():
        logger.error(f"❌ Directorio no encontrado: {target_directory}")
        return

    # Monitorear el directorio
    monitor_directory(str(target_directory), server_process)

if __name__ == "__main__":
    main()