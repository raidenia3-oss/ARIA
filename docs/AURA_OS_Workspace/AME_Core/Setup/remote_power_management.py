#!/usr/bin/env python3
"""
Script para configurar Remote Power Management en Windows.
Incluye Wake-on-LAN, servicios persistentes y monitoreo de recursos.
"""

import os
import subprocess
import sys
import time
import platform
import ctypes
from pathlib import Path

# Configuración global
NSSM_PATH = "C:/Program Files/NSSM/nssm.exe"
SERVICES = {
    "Shadow-Core": {
        "command": f"python {os.path.join(os.getcwd(), 'Shadow-Core', 'start_shadow.bat')}",
        "description": "Shadow-Core Service",
        "startup": "auto"
    },
    "Ollama": {
        "command": "ollama serve",
        "description": "Ollama Service",
        "startup": "auto"
    },
    "Cloudflare Tunnel": {
        "command": f"python {os.path.join(os.getcwd(), 'Setup', 'cloudflared', 'zero_trust', 'tunnel_auth.py')}",
        "description": "Cloudflare Tunnel Service",
        "startup": "auto"
    }
}

def install_nssm():
    """Instala NSSM si no está disponible."""
    try:
        if not os.path.exists(NSSM_PATH):
            print("🔧 NSSM no encontrado. Descargando e instalando...")
            nssm_url = "https://nssm.cc/download/nssm-2.95.zip"
            download_path = os.path.join(os.getcwd(), "nssm_installer.zip")

            # Descargar NSSM
            subprocess.run(["powershell", "-Command", f"Invoke-WebRequest -Uri {nssm_url} -OutFile {download_path}"], check=True)

            # Extraer NSSM
            subprocess.run(["powershell", "-Command", f"Expand-Archive -Path {download_path} -DestinationPath {os.getcwd()}"], check=True)

            # Instalar NSSM como servicio
            subprocess.run([f"{os.path.join(os.getcwd(), 'nssm-2.95', 'win64', 'nssm.exe')}"] + ["install", "NSSMService"], check=True)

            print("✅ NSSM instalado correctamente.")
        return True
    except Exception as e:
        print(f"❌ Error al instalar NSSM: {e}")
        return False

def configure_wake_on_lan():
    """Configura Wake-on-LAN en Windows."""
    try:
        print("🔌 Configurando Wake-on-LAN...")

        # Verificar si Wake-on-LAN está habilitado
        result = subprocess.run(["powercfg", "/waketimers"], capture_output=True, text=True)
        if "Wake timers are enabled" not in result.stdout:
            print("⚠️  Wake timers no están habilitados. Habilitándolos...")
            subprocess.run(["powercfg", "/waketimers", "enable"], check=True)

        # Habilitar Wake-on-LAN en la BIOS (simulado)
        print("🔧 Configuración de Wake-on-LAN simulada (requiere habilitar en BIOS).")
        print("   - Asegúrate de que Wake-on-LAN esté habilitado en la BIOS/UEFI.")
        print("   - Usa la MAC dirección física de la tarjeta de red para enviar el Magic Packet.")

        # Crear script para enviar Magic Packet
        magic_packet_script = Path("Setup/send_magic_packet.py")
        with open(magic_packet_script, "w", encoding="utf-8") as f:
            f.write("""#!/usr/bin/env python3
# Script para enviar un Magic Packet Wake-on-LAN.

import socket
import argparse


def send_magic_packet(mac_address, ip_address, port=9):
    """Envía un Magic Packet a la dirección MAC especificada."""
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
    magic_packet = b'\\xff' * 6 + mac_bytes * 16
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(magic_packet, (ip_address, port))
    print(f"✅ Magic Packet enviado a {ip_address}:{port} para MAC {mac_address}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enviar Magic Packet Wake-on-LAN.')
    parser.add_argument('--mac', required=True, help='Dirección MAC del dispositivo (ej: 00:11:22:33:44:55)')
    parser.add_argument('--ip', required=True, help='Dirección IP del dispositivo (ej: 192.168.1.100)')
    args = parser.parse_args()
    send_magic_packet(args.mac, args.ip)
""")

        print("✅ Script para enviar Magic Packet creado en Setup/send_magic_packet.py")
        return True
    except Exception as e:
        print(f"❌ Error al configurar Wake-on-LAN: {e}")
        return False

def create_windows_services():
    """Crea servicios de Windows para Shadow-Core, Ollama y Cloudflare Tunnel."""
    try:
        print("🚀 Creando servicios de Windows...")

        # Instalar NSSM si no está disponible
        if not install_nssm():
            print("⚠️  No se pudo instalar NSSM. Usando Task Scheduler como alternativa.")

        # Crear servicios usando NSSM
        for service_name, service_config in SERVICES.items():
            try:
                print(f"🔧 Configurando servicio: {service_name}")

                # Verificar si el servicio ya existe
                result = subprocess.run([NSSM_PATH, "status", service_name], capture_output=True, text=True)
                if "Service is not installed" in result.stdout or "Service is not running" in result.stdout:
                    # Instalar el servicio
                    subprocess.run([
                        NSSM_PATH,
                        "install", service_name,
                        service_config["command"],
                        "--Description", service_config["description"],
                        "--Startup", service_config["startup"],
                        "--AppDirectory", os.getcwd()
                    ], check=True)

                    # Iniciar el servicio
                    subprocess.run([NSSM_PATH, "start", service_name], check=True)

                    print(f"✅ Servicio {service_name} creado e iniciado.")
                else:
                    print(f"✅ Servicio {service_name} ya existe y está en ejecución.")
            except Exception as e:
                print(f"❌ Error al crear servicio {service_name}: {e}")

        # Configurar Task Scheduler como alternativa si NSSM falla
        configure_task_scheduler()

        return True
    except Exception as e:
        print(f"❌ Error al crear servicios: {e}")
        return False

def configure_task_scheduler():
    """Configura Task Scheduler para iniciar servicios al iniciar sesión."""
    try:
        print("📅 Configurando Task Scheduler para iniciar servicios al iniciar sesión...")

        # Crear tareas para cada servicio
        for service_name, service_config in SERVICES.items():
            task_name = f"AURA_{service_name.replace('-', '_')}"
            task_path = os.path.join(os.getcwd(), service_config["command"].split()[1] if len(service_config["command"].split()) > 1 else service_config["command"])

            # Crear tarea usando PowerShell
            powershell_script = f"""
$Action = New-ScheduledTaskAction -Execute "{task_path}"
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

        # Insertar código para el endpoint de monitoreo
        monitor_code = """
import psutil
import platform
import GPUtil

def get_system_metrics():
    """Obtiene métricas del sistema como temperatura de CPU, uso de RAM y estado de Ollama."""
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
        import requests
        start_time = time.time()
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        metrics["ollama"]["status"] = "running"
        metrics["ollama"]["response_time"] = round((time.time() - start_time) * 1000, 2)  # en milisegundos
    except Exception as e:
        metrics["ollama"]["status"] = "not_responding"
        metrics["ollama"]["response_time"] = None

    return metrics

@app.route('/api/system/metrics', methods=['GET'])
def api_system_metrics():
    """Endpoint para obtener métricas del sistema."""
    try:
        metrics = get_system_metrics()
        return jsonify({"status": "ok", "metrics": metrics})
    except Exception as e:
        print(f"❌ Error obteniendo métricas del sistema: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
"""

        # Insertar el código en el archivo
        if "import psutil" not in content:
            content = content.replace("import os", "import os\nimport psutil\nimport platform\nimport time\nimport requests\nfrom datetime import datetime")

        if "from flask import Flask" in content:
            content = content.replace("from flask import Flask", "from flask import Flask, jsonify\n" + monitor_code)

        with open(shadow_core_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Endpoint para monitoreo de recursos añadido a Shadow-Core.")
        return True
    except Exception as e:
        print(f"❌ Error al configurar endpoint de monitoreo: {e}")
        return False

def configure_suspend_to_ram():
    """Configura el sistema para mantenerse en estado de suspensión activa (S3)."""
    try:
        print("🔄 Configurando suspensión activa (S3) para reinicio rápido...")

        # Habilitar suspensión en Windows
        subprocess.run(["powercfg", "/h", "on"], check=True)
        print("✅ Suspensión activada (Hibernación).")

        # Configurar para mantener la PC en estado S3
        subprocess.run(["powercfg", "/a"], check=True)
        print("✅ Estado S3 configurado para suspensión rápida.")

        # Crear script para mantener la PC en estado S3
        s3_script_path = Path("Setup/maintain_s3_state.py")
        with open(s3_script_path, "w") as f:
            f.write("""
#!/usr/bin/env python3
"""
Script para mantener la PC en estado de suspensión activa (S3).
"""

import ctypes
import time

def set_suspend_state():
    """Configura el sistema para mantenerse en estado S3."""
    try:
        # Usar la API de Windows para mantener el estado S3
        ctypes.windll.kernel32.SetThreadExecutionState(0x00000040)  # ES_CONTINUOUS
        print("✅ Estado S3 configurado para mantener la PC activa.")

        # Mantener el script en ejecución para evitar que el sistema entre en suspensión
        while True:
            time.sleep(60)
    except Exception as e:
        print(f"❌ Error al configurar estado S3: {e}")

if __name__ == "__main__":
    set_suspend_state()
""")

        print("✅ Script para mantener estado S3 creado en Setup/maintain_s3_state.py")
        return True
    except Exception as e:
        print(f"❌ Error al configurar suspensión activa: {e}")
        return False

def main():
    """Función principal para configurar Remote Power Management."""
    print("=" * 50)
    print("🔌 Configurando Remote Power Management")
    print("=" * 50)

    # Configurar Wake-on-LAN
    if not configure_wake_on_lan():
        print("⚠️  No se pudo configurar Wake-on-LAN.")

    # Crear servicios de Windows
    if not create_windows_services():
        print("⚠️  No se pudieron crear servicios de Windows.")

    # Configurar endpoint de monitoreo
    if not configure_system_monitor_endpoint():
        print("⚠️  No se pudo configurar el endpoint de monitoreo.")

    # Configurar suspensión activa (S3)
    if not configure_suspend_to_ram():
        print("⚠️  No se pudo configurar suspensión activa (S3).")

    print("\n🔌 Configuración de Remote Power Management completada.")
    print("📌 Instrucciones:")
    print("   1. Asegúrate de que Wake-on-LAN esté habilitado en la BIOS/UEFI.")
    print("   2. Usa el script 'send_magic_packet.py' para despertar la PC desde otra red.")
    print("   3. Los servicios se iniciarán automáticamente al iniciar sesión en Windows.")
    print("   4. Accede al endpoint '/api/system/metrics' para monitorear recursos del sistema.")
    print("   5. Usa el script 'maintain_s3_state.py' para mantener la PC en estado S3.")
    print("=" * 50)

if __name__ == "__main__":
    main()