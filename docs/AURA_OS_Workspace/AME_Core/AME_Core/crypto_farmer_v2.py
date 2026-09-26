# crypto_farmer_v2.py
# Módulo de granjeo de criptomonedas para el proyecto AURA.
# Integra playwright para control avanzado y lógica de juego mejorada.

import os
import json
import time
import random
import requests
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, expect

# Cargar variables de entorno
BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

# --- Configuración (Puedes mover esto a un archivo config.json) ---
CONFIG = {
    "rollercoin": {
        "url_base": "https://rollercoin.com",
        "refresh_token": os.environ.get("RC_REFRESH_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uX2lkIjoiNjllZTRlNWFkMjhhMGQyNDgwZTAxNTM1IiwidG9rZW4iOiIyNzc4MWVhMi00NmRiLTRkMjUtYjE2Zi00NTVhYTYxMTFkNjYiLCJpYXQiOjE3Nzc3NzMxMDEsImV4cCI6MTgwOTMzMDcwMX0.5p4HchSBTMTr7B5LrgcniVo4YCeIbnJIL9co8k24kH8"),
        "whatsapp_number": os.environ.get("RC_WHATSAPP_NUMBER", "+51 942858492"),
        "whatsapp_apikey": os.environ.get("RC_WHATSAPP_APIKEY", "6272348"),
        "headless": False, # Pon en False para depurar
        "juegos_a_jugar": 3, # Cuántos juegos por ciclo
        "tiempo_espera_ciclo": 3600 # 1 hora entre ciclos
    }
}

class CryptoFarmer:
    def __init__(self, config):
        self.config = config['rollercoin']
        self.browser = None
        self.context = None
        self.page = None
        self.report = []

    def log(self, mensaje, tipo="INFO"):
        """Función de logging que también añade al reporte."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{tipo}] {mensaje}")
        self.report.append(f"{mensaje}")

    def send_whatsapp(self, msg):
        """Envía un reporte por WhatsApp."""
        if not self.config['whatsapp_number'] or not self.config['whatsapp_apikey']:
            self.log("WhatsApp no configurado.", "AVISO")
            return
        try:
            requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": self.config['whatsapp_number'], "text": msg, "apikey": self.config['whatsapp_apikey']},
                timeout=10
            )
            self.log("Reporte enviado por WhatsApp.", "EXITO")
        except Exception as e:
            self.log(f"Error al enviar WhatsApp: {e}", "ERROR")

    def start_session(self):
        """Inicia el navegador y la sesión en Rollercoin."""
        self.log("Iniciando sesión de granjeo...")
        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=self.config['headless'])
            self.context = self.browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            self.page = self.context.new_page()

            # Inyectar refreshToken para login automático
            self.page.goto(self.config['url_base'])
            self.page.evaluate(f"localStorage.setItem('refreshToken', '{self.config['refresh_token']}');")
            
            self.page.goto(f"{self.config['url_base']}/dashboard", timeout=30000)
            
            # Verificar si el login fue exitoso
            try:
                expect(self.page).to_have_url(f"{self.config['url_base']}/dashboard")
                self.log("Sesión iniciada con éxito.", "EXITO")
                self.run_cycle()
            except:
                self.log("Fallo en el inicio de sesión.", "ERROR")
                self.final_report()
            finally:
                self.browser.close()

    def claim_daily_reward(self):
        """Reclama la recompensa diaria si está disponible."""
        try:
            claim_button = self.page.get_by_text("Claim").first
            if claim_button.is_visible():
                claim_button.click()
                self.page.wait_for_timeout(2000)
                self.log("Recompensa diaria reclamada.", "EXITO")
                return True
        except:
            self.log("Recompensa diaria no disponible o ya reclamada.", "AVISO")
        return False

    def play_game_intelligently(self):
        """Lógica de juego mejorada. ¡Aquí está la clave!"""
        self.log("Iniciando minijuego con lógica inteligente...")
        
        # Esperar a que el juego cargue
        self.page.wait_for_timeout(3000)
        
        # EJEMPLO: Lógica para un juego de "hacer clic"
        # Necesitarás inspeccionar el HTML del juego para encontrar los selectores correctos.
        # Por ejemplo, si el juego tiene una cuadrícula de bloques:
        try:
            game_container = self.page.locator(".game-canvas").first # Selector hipotético
            expect(game_container).to_be_visible(timeout=5000)

            # Bucle de juego por 60 segundos
            end_time = time.time() + 60
            while time.time() < end_time:
                # Buscar elementos con los que interactuar (ej: bloques dorados, monedas)
                # clickable_elements = self.page.locator(".golden-block").all()
                # for element in clickable_elements:
                #     if element.is_visible():
                #         element.click()
                #         self.page.wait_for_timeout(random.uniform(100, 300)) # Simular reacción humana
                
                # Lógica de fallback por si no encuentra los elementos específicos
                self.page.mouse.click(random.randint(100, 800), random.randint(200, 600))
                self.page.wait_for_timeout(random.uniform(0.5, 1.5))
            
            self.log("Minijuego completado.", "EXITO")
            return True
        except Exception as e:
            self.log(f"Error en la lógica del juego: {e}", "ERROR")
            return False

    def run_cycle(self):
        """Ejecuta el ciclo completo de granjeo."""
        self.claim_daily_reward()
        
        self.page.goto(f"{self.config['url_base']}/game/choose_game", timeout=30000)
        self.page.wait_for_timeout(4000)
        
        juegos_completados = 0
        start_buttons = self.page.locator("button:has-text('START')").all()
        
        for i, btn in enumerate(start_buttons[:self.config['juegos_a_jugar']]):
            try:
                self.log(f"Iniciando juego {i+1}...")
                btn.click()
                self.page.wait_for_url("**/play_game**", timeout=10000)
                if self.play_game_intelligently():
                    juegos_completados += 1
                self.page.goto(f"{self.config['url_base']}/game/choose_game", timeout=30000)
                self.page.wait_for_timeout(3000)
            except Exception as e:
                self.log(f"Error al iniciar el juego {i+1}: {e}", "ERROR")
        
        self.log(f"Ciclo finalizado. Juegos completados: {juegos_completados}")
        self.final_report()

    def final_report(self):
        """Genera y envía el reporte final."""
        self.report.append("--- FIN DEL REPORTE ---")
        final_message = "\n".join(self.report)
        print("\n" + final_message)
        self.send_whatsapp(final_message)

if __name__ == "__main__":
    farmer = CryptoFarmer(CONFIG)
    farmer.start_session()