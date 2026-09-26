import requests
import time
import schedule
import sys
import os

N8N_URL = os.environ.get("N8N_URL", "https://n8n-onme.onrender.com")


def ping():
    try:
        r = requests.get(N8N_URL, timeout=10)
        print(f"N8N ping: {r.status_code}", flush=True)
    except Exception as e:
        print(f"N8N offline: {e}", flush=True)


# Ping cada 10 minutos
schedule.every(10).minutes.do(ping)

print(f"Manteniendo N8N activo: {N8N_URL}", flush=True)
ping()  # ping inmediato al iniciar

while True:
    schedule.run_pending()
    time.sleep(60)
