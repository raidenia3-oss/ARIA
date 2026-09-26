#!/usr/bin/env python3
"""
NOD_NETWORK_CHECK.py - Módulo Venice para realizar un chequeo básico de red (ping).
Este módulo toma una dirección IP o nombre de host como argumento y realiza un ping.
"""

import sys
import subprocess
import platform
import json
import time

def run_ping(target_host, count=4):
    """
    Ejecuta un comando ping y devuelve el resultado.
    """
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, str(count), target_host]
    
    try:
        start_time = time.time()
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        end_time = time.time()
        execution_time = round(end_time - start_time, 2)

        output = result.stdout.strip()
        error = result.stderr.strip()
        
        status = "success" if result.returncode == 0 else "error"
        message = f"Ping a {target_host} completado." if status == "success" else f"Error al hacer ping a {target_host}."

        return {
            "status": status,
            "module": "NOD_NETWORK_CHECK.py",
            "target": target_host,
            "returncode": result.returncode,
            "stdout": output,
            "stderr": error,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": execution_time
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "module": "NOD_NETWORK_CHECK.py",
            "target": target_host,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Tiempo de espera excedido al hacer ping a {target_host}.",
            "message": f"Tiempo de espera excedido al hacer ping a {target_host}.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": 10.0
        }
    except Exception as e:
        return {
            "status": "error",
            "module": "NOD_NETWORK_CHECK.py",
            "target": target_host,
            "returncode": 1,
            "stdout": "",
            "stderr": str(e),
            "message": f"Error inesperado: {str(e)}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "execution_time": 0.0
        }

def main():
    if len(sys.argv) < 2:
        response = {
            "status": "error",
            "module": "NOD_NETWORK_CHECK.py",
            "message": "Uso: python NOD_NETWORK_CHECK.py <target_host> [ping_count]",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        print(json.dumps(response))
        sys.exit(1)

    target_host = sys.argv[1]
    ping_count = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 4

    result = run_ping(target_host, ping_count)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
