#!/usr/bin/env python3
"""
RollerCoin Bot - Versión Automatizada con Integración Gmail
Bot automatizado para RollerCoin con lectura automática de códigos de verificación

Parte del sistema AURA-OS
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rollercoin_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RollerCoinBot')

class RollerCoinBot:
    """Bot automatizado de RollerCoin con integración Gmail"""

    def __init__(self):
        self.gmail_reader = None
        self.running = False
        self.last_code_time = None
        self.config = self.load_config()

    def load_config(self):
        """Carga configuración desde variables de entorno y knowledge base"""
        from dotenv import load_dotenv
        load_dotenv()

        # Configuración base desde variables de entorno
        config = {
            'check_interval': int(os.getenv('ROLLERCOIN_CHECK_INTERVAL', '60')),
            'max_retries': int(os.getenv('ROLLERCOIN_MAX_RETRIES', '3')),
            'game_url': os.getenv('ROLLERCOIN_GAME_URL', 'https://rollercoin.com'),
            'enable_gmail': os.getenv('ROLLERCOIN_ENABLE_GMAIL', 'true').lower() == 'true',
            'wait_times': {
                'login': int(os.getenv('ROLLERCOIN_WAIT_LOGIN', '10')),
                'game_load': int(os.getenv('ROLLERCOIN_WAIT_GAME_LOAD', '15')),
                'action': int(os.getenv('ROLLERCOIN_WAIT_ACTION', '5')),
                'captcha': int(os.getenv('ROLLERCOIN_WAIT_CAPTCHA', '30'))
            }
        }

        # Cargar configuración desde knowledge base
        self._load_knowledge_base_config(config)

        return config

    def _load_knowledge_base_config(self, config: dict):
        """Carga configuración adicional desde knowledge base"""
        try:
            from Automation_Bots.analyzer import ErrorAnalyzer
            analyzer = ErrorAnalyzer()
            kb_config = analyzer.get_current_config()

            # Actualizar configuración con valores de knowledge base
            if 'check_interval' in kb_config:
                config['check_interval'] = kb_config['check_interval']

            if 'max_retries' in kb_config:
                config['max_retries'] = kb_config['max_retries']

            if 'wait_times' in kb_config:
                for key, value in kb_config['wait_times'].items():
                    if key in config['wait_times']:
                        config['wait_times'][key] = value

            logger.info("✅ Configuración cargada desde knowledge base")

        except Exception as e:
            logger.warning(f"⚠️  No se pudo cargar configuración desde knowledge base: {str(e)}")
            logger.info("Usando configuración por defecto")

    def initialize_gmail_reader(self):
        """Inicializa el lector de Gmail"""
        if not self.config['enable_gmail']:
            logger.info("Integración con Gmail deshabilitada")
            return False

        try:
            from rollercoin.gmail_reader import RollerCoinGmailReader
            self.gmail_reader = RollerCoinGmailReader()
            logger.info("✅ Integración con Gmail inicializada")
            return True
        except ImportError as e:
            logger.error(f"No se pudo importar GmailReader: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inicializando GmailReader: {str(e)}")
            return False

    def get_verification_code(self) -> Optional[str]:
        """Obtiene código de verificación desde Gmail"""
        if not self.gmail_reader:
            logger.warning("GmailReader no disponible")
            return None

        try:
            code = self.gmail_reader.get_latest_verification_code()
            if code:
                self.last_code_time = datetime.now()
                logger.info(f"🔑 Código de verificación obtenido: {code}")
                return code
            else:
                logger.info("No se encontraron códigos de verificación")
                return None
        except Exception as e:
            logger.error(f"Error obteniendo código: {str(e)}")
            return None

    def check_game_status(self):
        """Verifica el estado del juego (simulado)"""
        # En una implementación real, esto verificaría el estado del juego web
        logger.info("🎮 Verificando estado del juego RollerCoin...")
        time.sleep(2)  # Simular verificación
        return True

    def perform_game_actions(self, code: Optional[str] = None):
        """Realiza acciones en el juego (simulado)"""
        if code:
            logger.info(f"🤖 Usando código de verificación: {code}")
            # En una implementación real, esto ingresaría el código en el juego
            time.sleep(3)  # Simular acción
            logger.info("✅ Código aplicado correctamente")
        else:
            logger.info("🤖 Realizando acciones estándar en el juego")
            time.sleep(5)  # Simular acciones de juego

    def monitor_game(self):
        """Monitorea y juega RollerCoin automáticamente"""
        logger.info("🚀 Iniciando bot de RollerCoin")
        self.running = True

        # Inicializar integración con Gmail
        gmail_ready = self.initialize_gmail_reader()

        while self.running:
            try:
                # Verificar estado del juego
                if not self.check_game_status():
                    logger.warning("El juego no está respondiendo")
                    time.sleep(self.config['check_interval'])
                    continue

                # Obtener código de verificación si está disponible
                code = None
                if gmail_ready:
                    code = self.get_verification_code()

                # Realizar acciones en el juego
                self.perform_game_actions(code)

                # Esperar antes de la próxima iteración
                time.sleep(self.config['check_interval'])

            except KeyboardInterrupt:
                logger.info("Bot detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en el bot: {str(e)}")
                time.sleep(min(self.config['check_interval'], 300))

    def start(self):
        """Inicia el bot"""
        try:
            self.monitor_game()
        except Exception as e:
            logger.error(f"Error crítico en el bot: {str(e)}")
            self.send_alert(f"RollerCoin Bot crashed: {str(e)}")
        finally:
            logger.info("Bot finalizado")

    def send_alert(self, message: str):
        """Envía una alerta"""
        logger.error(f"🚨 ALERTA: {message}")
        try:
            from AURA_Core.services.notification_service import NotificationService
            NotificationService().send_alert(f"RollerCoin Bot: {message}")
        except ImportError:
            # Fallback: escribir en log de alertas
            with open('alerts.log', 'a') as f:
                f.write(f"{datetime.now()} - RollerCoin Bot: {message}\n")

def main():
    """Punto de entrada principal"""
    bot = RollerCoinBot()

    # Modo de prueba
    if os.getenv('TEST_MODE') == 'true':
        logger.info("🧪 Modo de prueba activado")
        bot.initialize_gmail_reader()
        code = bot.get_verification_code()
        if code:
            print(f"Código obtenido: {code}")
        else:
            print("No se obtuvo código")
        return

    # Modo normal
    bot.start()

if __name__ == "__main__":
    main()