# hacker.py
# Módulo de seguridad y automatización de ingresos para AURA.
# Expone endpoints de API para controlar bots de granjeo.

import os
import time
from fastapi import HTTPException
from rollercoin_api_client import RollercoinAPIClient

# --- Configuración desde variables de entorno de Vercel/Railway ---
RC_REFRESH_TOKEN = os.environ.get("RC_REFRESH_TOKEN", "")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")
WHATSAPP_APIKEY = os.environ.get("WHATSAPP_APIKEY", "")

# --- Clase del Granjero de Cripto ---
class CryptoFarmer:
    def __init__(self):
        self.report = []
        self.config = {
            "refresh_token": RC_REFRESH_TOKEN,
            "whatsapp_number": WHATSAPP_NUMBER,
            "whatsapp_apikey": WHATSAPP_APIKEY,
        }
        self.client = RollercoinAPIClient()

    def log(self, mensaje, tipo="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] [{tipo}] {mensaje}"
        print(log_msg)
        self.report.append(log_msg)

    def send_whatsapp(self, msg):
        # (Mantén la función send_whatsapp que ya tenías)
        pass

    def run_cycle(self):
        """Ejecuta un ciclo completo de granjeo usando el cliente de la API."""
        self.log("🚀 Iniciando ciclo de granjeo de Rollercoin...")
        final_report = {"status": "running", "details": []}

        if not RC_REFRESH_TOKEN:
            self.log("RC_REFRESH_TOKEN no configurado.", "ERROR")
            raise HTTPException(status_code=500, detail="RC_REFRESH_TOKEN no configurado en el servidor.")

        try:
            if not self.client.authenticate():
                raise HTTPException(status_code=500, detail="Fallo de autenticación en Rollercoin.")

            stats = self.client.get_user_stats()
            if stats is None:
                raise HTTPException(status_code=500, detail="No se pudieron obtener las estadísticas de Rollercoin.")

            self.log("✅ Stats de usuario obtenidas.", "EXITO")
            final_report["details"].append("✅ Stats de usuario obtenidas.")

            result = self.client.play_game_and_submit_score("mine_game", 5000)
            final_report["details"].append(result)

            if result.get("status") == "success":
                final_report["status"] = "completed"
                self.log("🏁 Ciclo de granjeo finalizado con éxito.")
            else:
                final_report["status"] = "failed"
                final_report["error"] = result.get("message")
                self.log(f"Error en el ciclo de granjeo: {result.get('message')}", "ERROR")

        except HTTPException:
            raise
        except Exception as e:
            self.log(f"Error crítico en el ciclo: {e}", "ERROR")
            final_report["status"] = "failed"
            final_report["error"] = str(e)

        final_report["full_log"] = self.report
        return final_report

# --- Instancia global del granjero para que la API la use ---
crypto_farmer_instance = CryptoFarmer()

# --- Funciones que serán expuestas como endpoints en index.py ---
def start_rollercoin_farmer():
    """Inicia un ciclo de granjeo y devuelve el reporte."""
    report = crypto_farmer_instance.run_cycle()
    crypto_farmer_instance.send_whatsapp("AURA: Ciclo de Rollercoin completado.")
    return report


def get_farmer_status():
    """Devuelve el último estado conocido del granjero."""
    return {"status": "idle", "last_report": crypto_farmer_instance.report[-5:] if crypto_farmer_instance.report else []}
