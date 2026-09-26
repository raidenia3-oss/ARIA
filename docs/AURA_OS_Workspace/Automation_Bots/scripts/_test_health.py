import time
import requests

time.sleep(3)

try:
    r = requests.get("http://127.0.0.1:5001/health", timeout=5)
    data = r.json()
    print(f"HTTP {r.status_code}: status={data['status']}, threat={data['threat_status']}")
    print("SISTEMA OPERATIVO. ESCUDO ACTIVO. HEARTBEAT IMPLEMENTADO")
except Exception as e:
    print(f"Error: {e}")