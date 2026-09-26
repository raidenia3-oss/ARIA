import os
import sys
import time
import requests
import json
from datetime import datetime

# Resolve paths correctly relative to the project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

STATUS_FILE = os.path.join(BASE_DIR, 'cache', 'connectivity_status.json')

def check_connectivity():
    try:
        # Check HTTP connectivity
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False

def update_status(online):
    data = {
        "online": online,
        "last_check": datetime.now().isoformat()
    }
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error guardando estado de conectividad: {e}")

def main():
    print("📶 Monitoreo de conectividad iniciado (Cada 5 minutos)...")
    error_count = 0
    max_errors = 3
    
    while True:
        online = check_connectivity()
        update_status(online)
        
        status_str = "🟢 ONLINE" if online else "🔴 OFFLINE"
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Conectividad: {status_str}")
        
        if not online:
            error_count += 1
            if error_count >= max_errors:
                print(f"⚠️ Alerta: Conexión fallida consecutivamente {error_count} veces.")
                # We do not abort the process since it's an offline-first assistant,
                # but we track the consecutive error count.
        else:
            error_count = 0
            
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDeteniendo monitor de conectividad.")
    except Exception as e:
        print(f"Error fatal en monitor de conectividad: {e}")
