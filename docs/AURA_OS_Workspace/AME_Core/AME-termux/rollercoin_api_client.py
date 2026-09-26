# rollercoin_api_client.py
# Cliente de la API de Rollercoin basado en los descubrimientos de "Coding With Mario".
# Este módulo se encargará de toda la comunicación directa con los servidores de Rollercoin.

import os
import time
import json
import requests
import hashlib
import random
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

# --- Configuración ---
RC_REFRESH_TOKEN = os.environ.get("RC_REFRESH_TOKEN", "")
BASE_URL = "https://rollercoin.com"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/game",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

class RollercoinAPIClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.access_token = None
        self.user_info = None

    def log(self, mensaje, tipo="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{tipo}] [API-Client] {mensaje}")

    def authenticate(self):
        """Obtiene un access_token válido usando el refresh_token."""
        self.log("Autenticando con la API de Rollercoin...")
        
        # Endpoint de autenticación (descubierto en el video)
        auth_url = f"{BASE_URL}/api/user/auth/token"
        
        payload = {"refreshToken": RC_REFRESH_TOKEN}
        
        try:
            response = self.session.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data.get("token")
            
            if not self.access_token:
                self.log("Fallo al obtener el token de acceso.", "ERROR")
                return False
                
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
            self.log("✅ Autenticación exitosa.", "EXITO")
            return True
            
        except requests.exceptions.RequestException as e:
            self.log(f"Error en la autenticación: {e}", "ERROR")
            return False

    def get_user_stats(self):
        """Obtiene las estadísticas del usuario."""
        if not self.access_token:
            if not self.authenticate():
                return None

        try:
            response = self.session.get(f"{BASE_URL}/api/user/stats", timeout=10)
            response.raise_for_status()
            self.user_info = response.json()
            self.log(f"Stats obtenidas: Power {self.user_info.get('power', 'N/A')}, RLT {self.user_info.get('balance', 'N/A')}")
            return self.user_info
        except requests.exceptions.RequestException as e:
            self.log(f"Error al obtener stats: {e}", "ERROR")
            return None

    def _generate_game_hash(self, score, game_id, nonce):
        """
        Genera el hash anti-trampas. La lógica clave.
        Basado en la ingeniería inversa del video de "Coding With Mario".
        ¡Puede que necesites ajustarla si Rollercoin lo cambia!
        """
        # La fórmula real debe ser extraída del código JS de Rollercoin.
        # Esto es un ejemplo basado en patrones comunes.
        message = f"{score}:{game_id}:{nonce}:RC_SALT"
        return hashlib.sha256(message.encode()).hexdigest()

    def play_game_and_submit_score(self, game_name, score_to_achieve):
        """
        Juega una partida de forma simulada y envía una puntuación.
        Esta es la función que te hará "infinito" en Rollercoin.
        """
        if not self.access_token:
            if not self.authenticate():
                return {"status": "error", "message": "No se pudo autenticar"}

        self.log(f"Iniciando partida de '{game_name}' para lograr {score_to_achieve} puntos.")

        try:
            start_url = f"{BASE_URL}/api/game/start"
            payload = {"game": game_name}
            start_response = self.session.post(start_url, json=payload, timeout=10)
            start_response.raise_for_status()
            game_data = start_response.json()
            
            game_id = game_data.get("id")
            nonce = game_data.get("nonce")
            
            if not game_id or not nonce:
                self.log("Fallo al iniciar la partida: no se recibió ID o nonce.", "ERROR")
                return {"status": "error", "message": "Fallo al iniciar partida"}

            self.log(f"Partida iniciada. ID: {game_id}, Nonce: {nonce}")

        except requests.exceptions.RequestException as e:
            self.log(f"Error al iniciar la partida: {e}", "ERROR")
            return {"status": "error", "message": str(e)}

        time_to_wait = random.uniform(50, 70)
        self.log(f"Simulando juego durante {time_to_wait:.2f} segundos...")
        time.sleep(time_to_wait)

        try:
            final_hash = self._generate_game_hash(score_to_achieve, game_id, nonce)
            
            submit_url = f"{BASE_URL}/api/game/end"
            payload = {
                "id": game_id,
                "score": score_to_achieve,
                "hash": final_hash
            }
            
            submit_response = self.session.post(submit_url, json=payload, timeout=10)
            submit_response.raise_for_status()
            
            result = submit_response.json()
            self.log(f"✅ Puntuación {score_to_achieve} enviada con éxito. Recompensa: {result.get('reward', 'N/A')}", "EXITO")
            return {"status": "success", "score": score_to_achieve, "reward": result.get('reward')}

        except requests.exceptions.RequestException as e:
            self.log(f"Error al enviar la puntuación: {e}", "ERROR")
            return {"status": "error", "message": f"Error al enviar puntuación: {e}"}

# --- Ejemplo de uso directo para pruebas ---
if __name__ == "__main__":
    client = RollercoinAPIClient()
    
    if client.authenticate():
        client.get_user_stats()
        result = client.play_game_and_submit_score("mine_game", 5000)
        print(result)
