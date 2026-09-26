#!/usr/bin/env python3
"""
AURA System Health Check - Monitor de salud del sistema
Verifica periódicamente el estado de todos los componentes críticos

Parte del sistema automatizado AURA-OS
"""

import os
import sys
import time
import requests
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system_health_check.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AURAHealthCheck')

class HealthCheck:
    """Servicio de monitoreo de salud del sistema AURA"""

    def __init__(self):
        self.services = {
            'backend': {
                'url': 'http://localhost:8000/api/status',
                'name': 'AURA Backend',
                'critical': True
            },
            'rollercoin_bot': {
                'process': 'rollercoin_bot.py',
                'name': 'RollerCoin Bot',
                'critical': True
            },
            'huggingface': {
                'url': 'https://raiden456-slut.hf.space/v1/ping',
                'name': 'Hugging Face Space',
                'critical': True
            },
            'gmail_service': {
                'module': 'AURA_Core.services.gmail_service',
                'name': 'Gmail Service',
                'critical': False
            }
        }
        self.last_check = None
        self.failure_count = {}
        self.max_failures = 3

    def check_http_endpoint(self, url: str, name: str) -> bool:
        """Verifica que un endpoint HTTP esté respondiendo"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code < 400:
                logger.info(f"✅ {name} está respondiendo (HTTP {response.status_code})")
                return True
            else:
                logger.warning(f"⚠️  {name} respondió con error (HTTP {response.status_code})")
                return False
        except requests.RequestException as e:
            logger.error(f"❌ {name} no está respondiendo: {str(e)}")
            return False

    def check_process_running(self, process_name: str, name: str) -> bool:
        """Verifica que un proceso esté en ejecución"""
        try:
            # Buscar proceso por nombre
            if sys.platform == 'win32':
                result = subprocess.run(
                    ['tasklist', '/FI', f'IMAGENAME eq {process_name}'],
                    capture_output=True,
                    text=True
                )
                return process_name in result.stdout
            else:
                result = subprocess.run(
                    ['pgrep', '-f', process_name],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
        except Exception as e:
            logger.error(f"❌ Error verificando proceso {name}: {str(e)}")
            return False

    def check_module_available(self, module_name: str, name: str) -> bool:
        """Verifica que un módulo Python esté disponible"""
        try:
            __import__(module_name)
            logger.info(f"✅ {name} está disponible")
            return True
        except ImportError as e:
            logger.error(f"❌ {name} no está disponible: {str(e)}")
            return False

    def check_service(self, service_name: str) -> bool:
        """Verifica un servicio específico"""
        service = self.services.get(service_name)
        if not service:
            logger.warning(f"Servicio desconocido: {service_name}")
            return False

        try:
            if 'url' in service:
                return self.check_http_endpoint(service['url'], service['name'])
            elif 'process' in service:
                return self.check_process_running(service['process'], service['name'])
            elif 'module' in service:
                return self.check_module_available(service['module'], service['name'])
            else:
                logger.warning(f"Servicio sin método de verificación: {service_name}")
                return False
        except Exception as e:
            logger.error(f"Error verificando {service['name']}: {str(e)}")
            return False

    def run_health_check(self) -> Dict[str, bool]:
        """Ejecuta verificación de salud de todos los servicios"""
        results = {}
        self.last_check = datetime.now()

        logger.info("🔍 Iniciando verificación de salud del sistema...")
        logger.info(f"Hora de verificación: {self.last_check}")

        for service_name, service in self.services.items():
            try:
                is_healthy = self.check_service(service_name)
                results[service_name] = is_healthy

                # Contar fallos
                if not is_healthy:
                    self.failure_count[service_name] = self.failure_count.get(service_name, 0) + 1
                    logger.warning(f"Fallo #{self.failure_count[service_name]} para {service['name']}")

                    # Reiniciar si supera el límite de fallos
                    if service.get('critical', False) and self.failure_count[service_name] >= self.max_failures:
                        self.handle_service_failure(service_name)
                else:
                    # Reiniciar contador si está saludable
                    self.failure_count[service_name] = 0

            except Exception as e:
                logger.error(f"Error en verificación de {service['name']}: {str(e)}")
                results[service_name] = False
                self.failure_count[service_name] = self.failure_count.get(service_name, 0) + 1

        return results

    def handle_service_failure(self, service_name: str):
        """Maneja fallos de servicios críticos"""
        service = self.services.get(service_name)
        if not service:
            return

        logger.error(f"🚨 {service['name']} ha fallado {self.max_failures} veces - Tomando acción...")

        try:
            if service_name == 'rollercoin_bot':
                self.restart_rollercoin_bot()
            elif service_name == 'backend':
                self.restart_backend()
            elif service_name == 'huggingface':
                self.notify_huggingface_issue()

            # Notificar fallo
            self.send_failure_notification(service_name)

        except Exception as e:
            logger.error(f"Error manejando fallo de {service['name']}: {str(e)}")

    def restart_rollercoin_bot(self):
        """Reinicia el bot de RollerCoin"""
        logger.info("🔄 Reiniciando RollerCoin Bot...")

        try:
            # Detener proceso existente
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq RollerCoin Bot'], shell=True)
            else:
                subprocess.run(['pkill', '-f', 'rollercoin_bot.py'])

            # Esperar y reiniciar
            time.sleep(5)

            # Iniciar nuevo proceso
            bot_path = Path(__file__).parent / 'rollercoin' / 'main.py'
            if bot_path.exists():
                subprocess.Popen([sys.executable, str(bot_path)], cwd=bot_path.parent)
                logger.info("✅ RollerCoin Bot reiniciado")
            else:
                logger.error("❌ No se encontró el archivo del bot")

        except Exception as e:
            logger.error(f"Error reiniciando RollerCoin Bot: {str(e)}")

    def restart_backend(self):
        """Reinicia el backend de AURA"""
        logger.info("🔄 Reiniciando AURA Backend...")

        try:
            # En producción, usar Railway API o systemd
            # Para desarrollo local:
            if os.getenv('RAILWAY_ENVIRONMENT') != 'production':
                backend_path = Path(__file__).parent / 'servidor_ame.py'
                if backend_path.exists():
                    subprocess.Popen([sys.executable, str(backend_path)])
                    logger.info("✅ Backend reiniciado (modo desarrollo)")
                else:
                    logger.error("❌ No se encontró el archivo del backend")
            else:
                logger.info("📝 En producción, el backend se reiniciará automáticamente por Railway")

        except Exception as e:
            logger.error(f"Error reiniciando backend: {str(e)}")

    def notify_huggingface_issue(self):
        """Notifica problemas con Hugging Face"""
        logger.warning("⚠️  Problemas de conexión con Hugging Face Space")
        logger.info("El servicio se recuperará automáticamente cuando el Space esté disponible")

    def send_failure_notification(self, service_name: str):
        """Envía notificación de fallo"""
        service = self.services.get(service_name)
        if not service:
            return

        message = f"🚨 ALERTA: {service['name']} ha fallado y se ha reiniciado"
        logger.error(message)

        # Enviar a sistema de notificaciones
        try:
            from AURA_Core.services.notification_service import NotificationService
            NotificationService().send_alert(message)
        except ImportError:
            # Fallback: escribir en log de alertas
            with open('alerts.log', 'a') as f:
                f.write(f"{datetime.now()} - {message}\n")

    def monitor_continuously(self, interval: int = 900):
        """Monitorea el sistema continuamente (cada 15 minutos por defecto)"""
        logger.info(f"🔍 Iniciando monitoreo continuo (intervalo: {interval}s)")

        while True:
            try:
                # Ejecutar verificación de salud
                results = self.run_health_check()

                # Contar servicios saludables
                healthy_count = sum(1 for status in results.values() if status)
                total_services = len(results)

                logger.info(f"📊 Estado del sistema: {healthy_count}/{total_services} servicios saludables")

                # Esperar antes de la próxima verificación
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Monitoreo detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en monitoreo continuo: {str(e)}")
                time.sleep(min(interval, 300))  # Esperar hasta 5 minutos

if __name__ == "__main__":
    # Configurar desde variables de entorno
    from dotenv import load_dotenv
    load_dotenv()

    health_check = HealthCheck()

    # Modo de prueba: ejecutar una verificación y salir
    if os.getenv('TEST_MODE') == 'true':
        results = health_check.run_health_check()
        healthy_count = sum(1 for status in results.values() if status)
        print(f"Servicios saludables: {healthy_count}/{len(results)}")
    else:
        # Modo normal: monitorear continuamente (cada 15 minutos)
        health_check.monitor_continuously(interval=900)