#!/usr/bin/env python3
"""
Script simplificado para configurar servicios de Windows y endpoint de monitoreo.
"""

import os
import subprocess
import sys
from pathlib import Path

def configure_system_monitor_endpoint():
    """Configura un endpoint en Shadow-Core para monitorear recursos del sistema."""
    try:
        print("📊 Configurando endpoint para monitoreo de recursos del sistema...")

        # Modificar el archivo shadow_core.py para añadir el endpoint
        shadow_core_path = Path("Shadow-Core/shadow_core.py")
        if not shadow_core_path.exists():
            print("❌ El archivo shadow_core.py no existe.")
            return False

        # Leer el contenido actual
        with open(shadow_core_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Insertar imports necesarios
        if "import psutil" not in content and "import platform" not in content:
            content = content.replace("import os", "import os\nimport psutil\nimport platform\nimport time\nimport requests\nfrom datetime import datetime")

        # Insertar función para obtener métricas del sistema
        if "def get_system_metrics" not in content:
            monitor_code = """
def get_system_metrics():
    \"\"\"Obtiene métricas del sistema como temperatura de CPU, uso de RAM y estado de Ollama.\"\"\"
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "temperature": None,
            "usage_percent": psutil.cpu_percent(interval=1),
            "cores": psutil.cpu_count(logical=True)
        },
        "ram": {
            "total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
            "available_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2),
            "used_percent": psutil.virtual_memory().percent
        },
        "ollama": {
            "status": "unknown",
            "response_time": None
        },
        "system": {
            "platform": platform.platform(),
            "system": platform.system(),
            "node_name": platform.node()
        }
    }

    # Obtener temperatura de CPU (Windows)
    try:
        if platform.system() == "Windows":
            import wmi
            w = wmi.WMI()
            for cpu in w.WmiMonitorTemperatureProbe():
                if cpu.CurrentReading is not None:
                    metrics["cpu"]["temperature"] = round(cpu.CurrentReading, 1)
                    break
    except Exception as e:
        print(f"⚠️  Error obteniendo temperatura de CPU: {e}")

    # Verificar estado de Ollama
    try:
        start_time = time.time()
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        metrics["ollama"]["status"] = "running"
        metrics["ollama"]["response_time"] = round((time.time() - start_time) * 1000, 2)  # en milisegundos
    except Exception as e:
        metrics["ollama"]["status"] = "not_responding"
        metrics["ollama"]["response_time"] = None

    return metrics
"""

            content = content.replace("def main():", monitor_code + "\n\ndef main():")

        # Insertar endpoint para métricas del sistema
        if "@app.route('/api/system/metrics')" not in content:
            endpoint_code = """
@app.route('/api/system/metrics', methods=['GET'])
def api_system_metrics():
    \"\"\"Endpoint para obtener métricas del sistema.\"\"\"
    try:
        metrics = get_system_metrics()
        return jsonify({"status": "ok", "metrics": metrics})
    except Exception as e:
        print(f"❌ Error obteniendo métricas del sistema: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
"""

            content = content.replace("app.run(", endpoint_code + "\n\napp.run(")

        with open(shadow_core_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Endpoint para monitoreo de recursos añadido a Shadow-Core.")
        return True
    except Exception as e:
        print(f"❌ Error al configurar endpoint de monitoreo: {e}")
        return False

def configure_task_scheduler():
    """Configura Task Scheduler para iniciar servicios al iniciar sesión."""
    try:
        print("📅 Configurando Task Scheduler para iniciar servicios al iniciar sesión...")

        # Crear tareas para Shadow-Core, Ollama y Cloudflare Tunnel
        services = [
            {
                "name": "Shadow-Core",
                "command": f"python {os.path.join(os.getcwd(), 'Shadow-Core', 'start_shadow.bat')}"
            },
            {
                "name": "Ollama",
                "command": "ollama serve"
            },
            {
                "name": "Cloudflare Tunnel",
                "command": f"python {os.path.join(os.getcwd(), 'Setup', 'cloudflared', 'zero_trust', 'tunnel_auth.py')}"
            }
        ]

        for service in services:
            task_name = f"AURA_{service['name'].replace('-', '_')}"
            command = service["command"]

            # Crear tarea usando PowerShell
            powershell_script = f"""
$Action = New-ScheduledTaskAction -Execute "{command}"
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "{task_name}" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Force
"""

            subprocess.run(["powershell", "-Command", powershell_script], check=True)
            print(f"✅ Tarea '{task_name}' configurada para iniciar al iniciar sesión.")

        return True
    except Exception as e:
        print(f"❌ Error al configurar Task Scheduler: {e}")
        return False

def main():
    """Función principal para configurar Remote Power Management."""
    print("=" * 50)
    print("🔌 Configurando Remote Power Management (Servicios y Monitoreo)")
    print("=" * 50)

    # Configurar endpoint de monitoreo
    if not configure_system_monitor_endpoint():
        print("⚠️  No se pudo configurar el endpoint de monitoreo.")

    # Configurar Task Scheduler
    if not configure_task_scheduler():
        print("⚠️  No se pudo configurar Task Scheduler.")

    print("\n🔌 Configuración de Remote Power Management completada.")
    print("📌 Instrucciones:")
    print("   1. Accede al endpoint '/api/system/metrics' para monitorear recursos del sistema.")
    print("   2. Los servicios se iniciarán automáticamente al iniciar sesión en Windows.")
    print("=" * 50)

if __name__ == "__main__":
    main()