#!/usr/bin/env python3
"""
AURA TELEMETRY ENGINE — Monitor de hardware en tiempo real
Inspirado en Glances: monitorea CPU/RAM de procesos del emulador,
puertos de red y ejecuta rutinas de liberación automática.
"""

import psutil
import subprocess
import time
import json
import os
import threading
from datetime import datetime
from pathlib import Path

ADB_PATH = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
BASE_DIR = Path(__file__).resolve().parent.parent
TELEMETRY_OUTPUT = BASE_DIR / "core" / "telemetry_state.json"

# Umbrales de alerta
RAM_THRESHOLD = 85  # % — Si se supera, ejecutar rutina de liberación
CPU_THRESHOLD = 90  # % — Si se supera, notificar
PORT_FREEZE_TIMEOUT = 5  # segundos — Si un puerto no responde en 5s, alertar

PROCESS_PATTERNS = [
    "emulator",
    "qemu-system",
    "adb",
    "java",
    "gradle",
    "node",
    "python",
]


def get_system_stats():
    """Obtiene estadísticas globales del sistema."""
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu,
            "count": psutil.cpu_count(),
            "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
        },
        "ram": {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        },
    }


def get_process_by_pattern(pattern):
    """Encuentra procesos que coincidan con un patrón."""
    matches = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            if pattern.lower() in proc.info["name"].lower():
                matches.append(
                    {
                        "pid": proc.info["pid"],
                        "name": proc.info["name"],
                        "ram_percent": round(proc.info["memory_percent"], 1),
                        "cpu_percent": round(proc.info["cpu_percent"], 1),
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return matches


def get_emulator_processes():
    """Obtiene procesos relevantes del emulador y herramientas AURA."""
    result = {}
    for pattern in PROCESS_PATTERNS:
        procs = get_process_by_pattern(pattern)
        if procs:
            result[pattern] = procs
    return result


def check_port_status(port):
    """Verifica si un puerto local está activo."""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", port))
        s.close()
        return result == 0
    except Exception:
        return False


def get_port_status():
    """Verifica el estado de puertos críticos."""
    ports = {5000: "FastAPI", 5555: "ADB", 8765: "GBrain", 11434: "Ollama"}
    result = {}
    for port, name in ports.items():
        result[str(port)] = {
            "name": name,
            "active": check_port_status(port),
            "status": "ONLINE" if check_port_status(port) else "OFFLINE",
        }
    return result


def check_adb_connection():
    """Verifica si hay dispositivos conectados por ADB."""
    try:
        result = subprocess.run(
            [ADB_PATH, "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        devices = [l for l in lines if "device" in l and "List" not in l]
        return len(devices) > 0, devices
    except Exception:
        return False, []


def get_android_clipboard():
    """Obtiene el portapapeles del dispositivo Android."""
    try:
        result = subprocess.run(
            [ADB_PATH, "shell", "service", "call", "clipboard", "1"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except Exception:
        return None


def set_android_clipboard(text):
    """Envía texto al portapapeles de Android."""
    try:
        subprocess.run(
            [ADB_PATH, "shell", "input", "text", text.replace(" ", "%s")],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def inject_text_android(text):
    """Inyecta texto directamente en Android via ADB input text."""
    try:
        escaped = text.replace(" ", "%s").replace('"', '\\"')
        subprocess.run(
            [ADB_PATH, "shell", "input", "text", f'"{escaped}"'],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def get_android_screenshot():
    """Captura screenshot del Android via ADB."""
    try:
        subprocess.run(
            [ADB_PATH, "shell", "screencap", "-p", "/sdcard/aura_screen.png"],
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            [ADB_PATH, "pull", "/sdcard/aura_screen.png", str(BASE_DIR / "core")],
            capture_output=True,
            timeout=10,
        )
        return str(BASE_DIR / "core" / "aura_screen.png")
    except Exception:
        return None


def cleanup_stuck_processes():
    """Rutina de liberación: mata procesos zombie o consumidores excesivos."""
    killed = []
    for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
        try:
            if proc.info["memory_percent"] > 50:
                proc.terminate()
                killed.append(f"{proc.info['name']}(PID:{proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return killed


def monitor_loop(interval=5):
    """Loop de monitoreo continuo. Ejecuta en hilo separado."""
    while True:
        try:
            stats = get_system_stats()
            ports = get_port_status()
            procs = get_emulator_processes()
            adb_ok, adb_devices = check_adb_connection()

            state = {
                "timestamp": datetime.now().isoformat(),
                "system": stats,
                "ports": ports,
                "processes": procs,
                "adb": {
                    "connected": adb_ok,
                    "devices": adb_devices,
                },
                "alerts": [],
            }

            # Verificar umbrales
            if stats["ram"]["percent"] > RAM_THRESHOLD:
                killed = cleanup_stuck_processes()
                state["alerts"].append(
                    {
                        "type": "RAM_CRITICAL",
                        "message": f"RAM al {stats['ram']['percent']}%",
                        "action": f"Procesos limpiados: {killed}",
                    }
                )

            if stats["cpu"]["percent"] > CPU_THRESHOLD:
                state["alerts"].append(
                    {
                        "type": "CPU_HIGH",
                        "message": f"CPU al {stats['cpu']['percent']}%",
                    }
                )

            for port, info in ports.items():
                if not info["active"] and port in ["5000"]:
                    state["alerts"].append(
                        {
                            "type": "PORT_DOWN",
                            "message": f"Puerto {port} ({info['name']}) caído",
                        }
                    )

            # Guardar estado
            with open(TELEMETRY_OUTPUT, "w") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

        except Exception as e:
            pass

        time.sleep(interval)


def get_full_telemetry():
    """Obtiene un snapshot completo de telemetría (para API)."""
    stats = get_system_stats()
    ports = get_port_status()
    procs = get_emulator_processes()
    adb_ok, adb_devices = check_adb_connection()

    return {
        "timestamp": datetime.now().isoformat(),
        "system": stats,
        "ports": ports,
        "processes": procs,
        "adb": {
            "connected": adb_ok,
            "devices": adb_devices,
        },
    }


def start_monitor_background(interval=5):
    """Inicia el monitor en un hilo de fondo."""
    t = threading.Thread(target=monitor_loop, args=(interval,), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print("=" * 55)
    print("  AURA TELEMETRY ENGINE v1.0")
    print("  Monitor de hardware en tiempo real")
    print("=" * 55)

    stats = get_system_stats()
    ports = get_port_status()
    procs = get_emulator_processes()
    adb_ok, adb_devices = check_adb_connection()

    print(f"\n📊 CPU: {stats['cpu']['percent']}% ({stats['cpu']['count']} cores)")
    print(
        f"💾 RAM: {stats['ram']['used_gb']}GB / {stats['ram']['total_gb']}GB"
        f" ({stats['ram']['percent']}%)"
    )
    print(f"💿 Disk: {stats['disk']['percent']}%")

    print(f"\n🔌 Puertos:")
    for port, info in ports.items():
        icon = "🟢" if info["active"] else "🔴"
        print(f"   {icon} :{port} — {info['name']} → {info['status']}")

    print(f"\n📱 ADB: {'🟢 Conectado' if adb_ok else '🔴 Sin conexión'}")
    for dev in adb_devices:
        print(f"   → {dev}")

    print(f"\n⚙️ Procesos relevantes:")
    for pattern, procs_list in procs.items():
        for p in procs_list:
            print(f"   [{p['pid']}] {p['name']} RAM:{p['ram_percent']}% CPU:{p['cpu_percent']}%")
