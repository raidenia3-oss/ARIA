#!/usr/bin/env python3
"""
Script para configurar manualmente los servicios y el endpoint de monitoreo en servidor_ame.py.
"""

import os
import sys
from pathlib import Path

def configure_system_monitor_endpoint():
    """Configura un endpoint en servidor_ame.py para monitorear recursos del sistema."""
    try:
        print("📊 Configurando endpoint para monitoreo de recursos del sistema en servidor_ame.py...")

        # Modificar el archivo servidor_ame.py para añadir el endpoint
        server_path = Path("AME_Core/servidor_ame.py")
        if not server_path.exists():
            print("❌ El archivo servidor_ame.py no existe.")
            return False

        # Leer el contenido actual
        with open(server_path, "r", encoding="utf-8") as f:
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

        with open(server_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Endpoint para monitoreo de recursos añadido a servidor_ame.py.")
        return True
    except Exception as e:
        print(f"❌ Error al configurar endpoint de monitoreo: {e}")
        return False

def create_startup_scripts():
    """Crea scripts de inicio para los servicios."""
    try:
        print("📁 Creando scripts de inicio para servicios...")

        # Crear script de inicio para Shadow-Core
        shadow_core_script = Path("Setup/start_shadow_service.bat")
        with open(shadow_core_script, "w") as f:
            f.write("@echo off\n"
                    ":: Script para iniciar Shadow-Core como servicio\n"
                    "start \"Shadow-Core\" cmd /c python Shadow-Core\\start_shadow.bat\n"
                    "echo Shadow-Core iniciado.\n")

        # Crear script de inicio para Ollama
        ollama_script = Path("Setup/start_ollama_service.bat")
        with open(ollama_script, "w") as f:
            f.write("@echo off\n"
                    ":: Script para iniciar Ollama como servicio\n"
                    "start \"Ollama\" cmd /c ollama serve\n"
                    "echo Ollama iniciado.\n")

        # Crear script de inicio para Cloudflare Tunnel
        tunnel_script = Path("Setup/start_tunnel_service.bat")
        with open(tunnel_script, "w") as f:
            f.write("@echo off\n"
                    ":: Script para iniciar Cloudflare Tunnel como servicio\n"
                    "start \"Cloudflare Tunnel\" cmd /c python Setup\\cloudflared\\zero_trust\\tunnel_auth.py\n"
                    "echo Cloudflare Tunnel iniciado.\n")

        print("✅ Scripts de inicio para servicios creados.")
        print("   - start_shadow_service.bat")
        print("   - start_ollama_service.bat")
        print("   - start_tunnel_service.bat")

        return True
    except Exception as e:
        print(f"❌ Error al crear scripts de inicio: {e}")
        return False

def provide_instructions():
    """Proporciona instrucciones para configurar manualmente los servicios."""
    print("\n📌 Instrucciones para configurar servicios manualmente:")
    print("   1. Copia los scripts creados en la carpeta Setup a una ubicación accesible.")
    print("   2. Configura Task Scheduler manualmente para ejecutar estos scripts al iniciar sesión:")
    print("      - start_shadow_service.bat")
    print("      - start_ollama_service.bat")
    print("      - start_tunnel_service.bat")
    print("   3. Asegúrate de que los scripts se ejecuten con privilegios de administrador.")
    print("   4. Accede al endpoint '/api/system/metrics' para monitorear recursos del sistema.")

def main():
    """Función principal para configurar Remote Power Management manualmente."""
    print("=" * 50)
    print("🔧 Configurando Remote Power Management (Manual)")
    print("=" * 50)

    # Configurar endpoint de monitoreo en servidor_ame.py
    if not configure_system_monitor_endpoint():
        print("⚠️  No se pudo configurar el endpoint de monitoreo.")

    # Crear scripts de inicio para servicios
    if not create_startup_scripts():
        print("⚠️  No se pudieron crear los scripts de inicio.")

    # Proporcionar instrucciones
    provide_instructions()

    print("\n🔧 Configuración manual de Remote Power Management completada.")
    print("=" * 50)

if __name__ == "__main__":
    main()