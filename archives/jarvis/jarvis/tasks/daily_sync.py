import os
import sys
import time
import schedule

# Resolve paths correctly relative to the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from jarvis_core import JARVISCore

def daily_sync():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando sincronización diaria a GitHub...")
    try:
        jarvis = JARVISCore()
        jarvis.sync_with_cloud()
        jarvis.close()
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error en daily_sync: {e}")

# Register cron rule
schedule.every().day.at("03:00").do(daily_sync)

print("⏰ Tarea de sincronización diaria iniciada (Programada para las 03:00 AM)...")
while True:
    try:
        schedule.run_pending()
        time.sleep(60)
    except KeyboardInterrupt:
        print("\nDeteniendo tarea de sincronización diaria.")
        break
    except Exception as e:
        print(f"Error en bucle de sync diario: {e}")
        time.sleep(60)
