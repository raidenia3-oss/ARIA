#!/usr/bin/env python3
"""
Script de inicio para Shadow-Core que ejecuta el Guardian Watchdog primero.
"""

import os
import sys
import subprocess
import time
import signal

def start_watchdog():
    """Inicia el Guardian Watchdog."""
    watchdog_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'watchdog.py')
    if not os.path.exists(watchdog_path):
        print(f"Error: No se encontró el archivo {watchdog_path}")
        return False

    try:
        print("🔍 Iniciando Guardian Watchdog...")
        watchdog_process = subprocess.Popen(
            [sys.executable, watchdog_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        print(f"✅ Guardian Watchdog iniciado con PID: {watchdog_process.pid}")
        return True
    except Exception as e:
        print(f"❌ Error al iniciar Guardian Watchdog: {e}")
        return False

def start_shadow_core():
    """Inicia el resto de Shadow-Core y el agente de investigación proactiva."""
    shadow_core_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shadow_core.py')
    proactive_research_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'proactive_research.py')

    # Iniciar agente de investigación proactiva
    try:
        print("🔍 Iniciando Proactive Research Agent...")
        research_process = subprocess.Popen(
            [sys.executable, proactive_research_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        print(f"✅ Proactive Research Agent iniciado con PID: {research_process.pid}")
    except Exception as e:
        print(f"⚠️  Error al iniciar Proactive Research Agent: {e}")

    # Iniciar Shadow-Core
    if not os.path.exists(shadow_core_path):
        print(f"Error: No se encontró el archivo {shadow_core_path}")
        return False

    try:
        print("🚀 Iniciando Shadow-Core...")
        shadow_process = subprocess.Popen(
            [sys.executable, shadow_core_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        print(f"✅ Shadow-Core iniciado con PID: {shadow_process.pid}")
        return True
    except Exception as e:
        print(f"❌ Error al iniciar Shadow-Core: {e}")
        return False

def main():
    """Función principal para iniciar Shadow-Core con el watchdog."""
    print("=" * 50)
    print("🔒 Shadow-Core System Initialization")
    print("=" * 50)

    # Iniciar el watchdog primero
    if not start_watchdog():
        print("🚨 Falló el inicio del Guardian Watchdog. Deteniendo el sistema.")
        sys.exit(1)

    # Esperar un momento para que el watchdog se estabilice
    time.sleep(5)

    # Iniciar Shadow-Core
    if not start_shadow_core():
        print("🚨 Falló el inicio de Shadow-Core. El sistema puede estar en riesgo.")
        sys.exit(1)

    print("=" * 50)
    print("🔒 Shadow-Core y Guardian Watchdog están en ejecución.")
    print("=" * 50)

if __name__ == "__main__":
    main()