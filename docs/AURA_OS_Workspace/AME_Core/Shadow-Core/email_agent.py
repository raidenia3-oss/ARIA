"""
Módulo para el agente de inteligencia de correo electrónico.
Conecta a una cuenta de correo IMAP, escanea correos importantes y envía alertas.
"""

import os
import imaplib
import email
from email.header import decode_header
import time
import threading
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailAgent:
    """
    Agente de inteligencia de correo electrónico que escanea la bandeja de entrada
    en busca de correos importantes y envía alertas.
    """

    def __init__(self):
        self.imap_server = os.getenv('EMAIL_IMAP_SERVER')
        self.imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))
        self.imap_ssl = os.getenv('EMAIL_IMAP_SSL', 'True').lower() == 'true'
        self.imap_username = os.getenv('EMAIL_IMAP_USERNAME')
        self.imap_password = os.getenv('EMAIL_IMAP_PASSWORD')
        self.inbox_folder = os.getenv('EMAIL_INBOX_FOLDER', 'INBOX')
        self.search_keywords = [kw.strip().lower() for kw in os.getenv('EMAIL_SEARCH_KEYWORDS', '').split(',') if kw.strip()]
        self.last_scan_time = None
        self.scan_interval = 15 * 60  # 15 minutos en segundos
        self.running = False
        self.thread = None

        # Configuración del modelo LLM para síntesis
        self.llm_model = "dolphin-llama3"
        self.llm_endpoint = "http://localhost:11434/api/generate"  # Endpoint de Ollama

        # Configuración para notificaciones push
        self.push_notification_endpoint = "http://localhost:5001/api/mobile-protocol"

    def connect_to_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """
        Conecta al servidor IMAP y autentica al usuario.

        Returns:
            imaplib.IMAP4_SSL: Objeto de conexión IMAP o None si falla.
        """
        try:
            if self.imap_ssl:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            else:
                mail = imaplib.IMAP4(self.imap_server, self.imap_port)

            mail.login(self.imap_username, self.imap_password)
            mail.select(self.inbox_folder)
            logger.info("Conexión IMAP exitosa.")
            return mail
        except Exception as e:
            logger.error(f"Error al conectar a IMAP: {e}")
            return None

    def search_emails(self, mail: imaplib.IMAP4_SSL, criteria: str = "UNSEEN") -> List[str]:
        """
        Busca correos en la bandeja de entrada según criterios.

        Args:
            mail (imaplib.IMAP4_SSL): Objeto de conexión IMAP.
            criteria (str): Criterios de búsqueda (ej: "UNSEEN").

        Returns:
            List[str]: Lista de IDs de correos que cumplen los criterios.
        """
        try:
            status, messages = mail.search(None, criteria)
            if status != "OK":
                logger.error(f"Error al buscar correos: {messages}")
                return []

            email_ids = messages[0].split()
            return email_ids
        except Exception as e:
            logger.error(f"Error al buscar correos: {e}")
            return []

    def fetch_email(self, mail: imaplib.IMAP4_SSL, email_id: str) -> Optional[email.message.Message]:
        """
        Obtiene un correo específico por su ID.

        Args:
            mail (imaplib.IMAP4_SSL): Objeto de conexión IMAP.
            email_id (str): ID del correo.

        Returns:
            email.message.Message: Objeto de correo o None si falla.
        """
        try:
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                logger.error(f"Error al obtener correo {email_id}: {msg_data}")
                return None

            raw_email = msg_data[0][1]
            return email.message_from_bytes(raw_email)
        except Exception as e:
            logger.error(f"Error al obtener correo {email_id}: {e}")
            return None

    def parse_email(self, email_msg: email.message.Message) -> Dict:
        """
        Analiza un correo y extrae información relevante.

        Args:
            email_msg (email.message.Message): Objeto de correo.

        Returns:
            Dict: Información parseada del correo.
        """
        subject, encoding = decode_header(email_msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")

        from_, _ = decode_header(email_msg.get("From", ""))[0]
        if isinstance(from_, bytes):
            from_ = from_.decode(encoding if encoding else "utf-8")

        date_str = email_msg.get("Date", "")
        date = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z") if date_str else None

        body = ""
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset)
                    break
        else:
            payload = email_msg.get_payload(decode=True)
            charset = email_msg.get_content_charset() or "utf-8"
            body = payload.decode(charset)

        return {
            "subject": subject,
            "from": from_,
            "date": date,
            "body": body,
            "is_read": email_msg.get("X-GM-RFC822MSGID", "").startswith("1")  # Simulación de correo leído
        }

    def summarize_email(self, email_data: Dict) -> str:
        """
        Sintetiza el contenido de un correo usando el modelo LLM.

        Args:
            email_data (Dict): Datos parseados del correo.

        Returns:
            str: Resumen del correo en 2 líneas.
        """
        try:
            prompt = f"""
            Resume el siguiente correo en 2 líneas con información clave:

            Asunto: {email_data['subject']}
            De: {email_data['from']}
            Cuerpo: {email_data['body'][:500]}...

            Resumen:
            """

            payload = {
                "model": self.llm_model,
                "prompt": prompt,
                "stream": False
            }

            response = requests.post(self.llm_endpoint, json=payload)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No se pudo generar un resumen.")
            else:
                logger.error(f"Error al llamar al modelo LLM: {response.text}")
                return "Error al procesar el correo."
        except Exception as e:
            logger.error(f"Error al sintetizar correo: {e}")
            return "Error al sintetizar el correo."

    def send_push_notification(self, summary: str, email_data: Dict) -> bool:
        """
        Envía una notificación push al dispositivo móvil.

        Args:
            summary (str): Resumen del correo.
            email_data (Dict): Datos del correo.

        Returns:
            bool: True si la notificación se envió correctamente, False en caso contrario.
        """
        try:
            payload = {
                "type": "email_alert",
                "summary": summary,
                "subject": email_data["subject"],
                "from": email_data["from"],
                "timestamp": email_data["date"].isoformat() if email_data["date"] else datetime.now().isoformat(),
                "is_important": True
            }

            headers = {
                "Content-Type": "application/json"
            }

            response = requests.post(
                self.push_notification_endpoint,
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                logger.info("Notificación push enviada correctamente.")
                return True
            else:
                logger.error(f"Error al enviar notificación push: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error al enviar notificación push: {e}")
            return False

    def scan_inbox(self) -> None:
        """
        Escanea la bandeja de entrada en busca de correos importantes.
        """
        mail = self.connect_to_imap()
        if not mail:
            return

        try:
            # Buscar correos no leídos
            email_ids = self.search_emails(mail, "UNSEEN")
            if not email_ids:
                logger.info("No hay correos no leídos.")
                return

            for email_id in email_ids:
                email_msg = self.fetch_email(mail, email_id)
                if not email_msg:
                    continue

                email_data = self.parse_email(email_msg)

                # Verificar si el correo contiene palabras clave importantes
                body_lower = email_data["body"].lower()
                subject_lower = email_data["subject"].lower()

                if any(keyword in subject_lower or keyword in body_lower for keyword in self.search_keywords):
                    logger.info(f"Correo importante detectado: {email_data['subject']}")

                    # Sintetizar el correo
                    summary = self.summarize_email(email_data)

                    # Enviar notificación push
                    if self.send_push_notification(summary, email_data):
                        logger.info(f"Notificación enviada para: {email_data['subject']}")
                    else:
                        logger.error(f"No se pudo enviar notificación para: {email_data['subject']}")

                    # Marcar como leído (simulado)
                    mail.store(email_id, '+FLAGS', '\\Seen')

            self.last_scan_time = datetime.now()
            logger.info(f"Escaneo completado a las {self.last_scan_time}. Próximo escaneo en {self.scan_interval // 60} minutos.")

        except Exception as e:
            logger.error(f"Error durante el escaneo de la bandeja de entrada: {e}")
        finally:
            try:
                mail.close()
                mail.logout()
            except:
                pass

    def start(self) -> None:
        """
        Inicia el agente de correo en un hilo separado.
        """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_agent, daemon=True)
            self.thread.start()
            logger.info("Agente de correo iniciado.")

    def _run_agent(self) -> None:
        """
        Ejecuta el agente en un bucle infinito, escaneando la bandeja de entrada cada X minutos.
        """
        while self.running:
            try:
                self.scan_inbox()
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error en el bucle del agente: {e}")
                time.sleep(self.scan_interval)

    def stop(self) -> None:
        """
        Detiene el agente de correo.
        """
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Agente de correo detenido.")

if __name__ == "__main__":
    agent = EmailAgent()
    agent.start()

    # Esperar para mantener el programa en ejecución
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()