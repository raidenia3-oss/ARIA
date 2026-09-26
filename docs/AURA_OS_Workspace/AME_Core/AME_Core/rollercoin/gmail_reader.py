#!/usr/bin/env python3
"""
RollerCoin Gmail Reader - Integración con servicio de Gmail
Lee códigos de verificación de RollerCoin desde Gmail usando la API de Gmail

Parte del sistema automatizado AURA-OS
"""

import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rollercoin_gmail_reader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RollerCoinGmailReader')

# Importar servicios de AURA
try:
    from AURA_Core.services.gmail_service import GmailService
    from AURA_Core.services.notification_service import NotificationService
    from AURA_Core.utils.config import load_config
except ImportError:
    # Fallback para desarrollo
    class GmailService:
        def __init__(self):
            self.service = None

        def get_emails(self, query: str, max_results: int = 5) -> List[Dict]:
            """Simula obtener emails para desarrollo"""
            return [{
                'id': '12345',
                'snippet': 'Your RollerCoin verification code is ABC123',
                'date': datetime.now().isoformat()
            }]

    class NotificationService:
        def send_alert(self, message: str):
            logger.info(f"ALERT: {message}")

    class Config:
        ROLLERCOIN_EMAIL_QUERY = "from:no-reply@rollercoin.com subject:verification"

    def load_config():
        return Config()

class RollerCoinGmailReader:
    """Servicio para leer códigos de verificación de RollerCoin desde Gmail"""

    def __init__(self):
        self.config = load_config()
        self.gmail_service = GmailService()
        self.notification_service = NotificationService()
        self.last_check_time = None
        self.active_codes = set()

        # Patrones de expresión regular para extraer códigos
        self.code_patterns = [
            r'\b([A-Z0-9]{6})\b',  # Código alfanumérico de 6 caracteres
            r'\b([A-Z]{3}[0-9]{3})\b',  # 3 letras + 3 números
            r'verification code:?\s*([A-Z0-9]{4,8})',  # Código después de "verification code"
            r'Your code is:?\s*([A-Z0-9]{4,8})'  # Código después de "Your code is"
        ]

    def extract_verification_codes(self, text: str) -> List[str]:
        """Extrae códigos de verificación del texto usando expresiones regulares"""
        codes = set()
        text_upper = text.upper()

        for pattern in self.code_patterns:
            matches = re.findall(pattern, text_upper)
            for match in matches:
                # Filtrar códigos válidos (solo letras y números, longitud 4-8)
                if re.match(r'^[A-Z0-9]{4,8}$', match):
                    codes.add(match)

        return sorted(codes, key=len, reverse=True)

    def get_recent_emails(self, minutes: int = 30) -> List[Dict]:
        """Obtiene emails recientes de RollerCoin"""
        try:
            # Buscar emails de los últimos X minutos
            time_threshold = datetime.now() - timedelta(minutes=minutes)
            query = f"{self.config.ROLLERCOIN_EMAIL_QUERY} after:{time_threshold.strftime('%Y/%m/%d')}"
            logger.info(f"Buscando emails con query: {query}")

            emails = self.gmail_service.get_emails(query, max_results=10)
            logger.info(f"Encontrados {len(emails)} emails recientes de RollerCoin")
            return emails

        except Exception as e:
            logger.error(f"Error obteniendo emails: {str(e)}")
            self.notification_service.send_alert(f"GmailReader Error: {str(e)}")
            return []

    def process_emails(self, emails: List[Dict]) -> List[str]:
        """Procesa emails y extrae códigos de verificación"""
        new_codes = []

        for email in emails:
            email_id = email.get('id')
            snippet = email.get('snippet', '')
            date_str = email.get('date', '')

            # Extraer códigos del snippet
            codes = self.extract_verification_codes(snippet)

            for code in codes:
                if code not in self.active_codes:
                    self.active_codes.add(code)
                    new_codes.append(code)
                    logger.info(f"Nuevo código encontrado: {code} (Email ID: {email_id})")
                else:
                    logger.debug(f"Código duplicado ignorado: {code}")

        return new_codes

    def get_latest_verification_code(self) -> Optional[str]:
        """Obtiene el código de verificación más reciente"""
        try:
            # Obtener emails de los últimos 30 minutos
            emails = self.get_recent_emails(minutes=30)

            if not emails:
                logger.info("No se encontraron emails recientes de RollerCoin")
                return None

            # Procesar emails y obtener códigos
            new_codes = self.process_emails(emails)

            if new_codes:
                # Devolver el código más largo (probablemente el más reciente)
                latest_code = new_codes[0]
                logger.info(f"Último código de verificación: {latest_code}")
                return latest_code
            else:
                logger.info("No se encontraron nuevos códigos de verificación")
                return None

        except Exception as e:
            logger.error(f"Error obteniendo código de verificación: {str(e)}")
            self.notification_service.send_alert(f"GmailReader Error: {str(e)}")
            return None

    def monitor_inbox(self, interval: int = 60):
        """Monitorea el buzón en busca de nuevos códigos"""
        logger.info(f"Iniciando monitor de Gmail para RollerCoin (intervalo: {interval}s)")
        self.last_check_time = datetime.now()

        while True:
            try:
                # Obtener el código más reciente
                code = self.get_latest_verification_code()

                if code:
                    # Notificar que se encontró un nuevo código
                    message = f"Nuevo código de RollerCoin: {code}"
                    self.notification_service.send_alert(message)
                    logger.info(message)

                # Esperar antes de la próxima verificación
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Monitoreo detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en monitoreo: {str(e)}")
                time.sleep(min(interval, 300))  # Esperar hasta 5 minutos en caso de error

if __name__ == "__main__":
    # Configurar desde variables de entorno
    from dotenv import load_dotenv
    load_dotenv()

    reader = RollerCoinGmailReader()

    # Modo de prueba: obtener un código y salir
    if os.getenv('TEST_MODE') == 'true':
        code = reader.get_latest_verification_code()
        if code:
            print(f"Código encontrado: {code}")
        else:
            print("No se encontraron códigos")
    else:
        # Modo normal: monitorear continuamente
        reader.monitor_inbox(interval=60)