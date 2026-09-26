#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AURA Emergency Stop — Force Kill Script
Detiene procesos en bucle (pm2, python, node, cmd) de forma fulminante.
"""
import os
import sys
import subprocess
import signal
import time

def kill_processes_by_name(names):
    """Mata procesos por nombre (cross-platform)."""
    killed = []
    for name in names:
        try:
            if os.name == 'nt':  # Windows
                cmd = f'taskkill /f /im {name} 2>nul'
                subprocess.run(cmd, shell=True, check=False)
                killed.append(name)
            else:  # Unix
                cmd = f'pkill -f {name}'
                subprocess.run(cmd, shell=True, check=False)
                killed.append(name)
        except Exception as e:
            print(f"⚠️  Error matando {name}: {e}")
    return killed

def kill_pm2_daemon():
    """Mata el daemon de PM2 y limpia procesos."""
    try:
        # Matar daemon de PM2
        if os.name == 'nt':
            subprocess.run('pm2 kill', shell=True, check=False)
        else:
            subprocess.run('pm2 kill', shell=True, check=False)
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"⚠️  Error matando PM2 daemon: {e}")
        return False

def main():
    """Fuerza parada de emergencia."""
    print("🔴 [AURA EMERGENCY STOP] Iniciando contención...")

    # Lista de procesos a matar
    targets = ['python.exe', 'python', 'node.exe', 'node', 'cmd.exe', 'pm2.exe', 'pm2']

    # 1. Matar procesos por nombre
    killed = kill_processes_by_name(targets)
    print(f"✅ Procesos matados: {', '.join(killed) if killed else 'Ninguno'}")

    # 2. Matar daemon de PM2
    pm2_killed = kill_pm2_daemon()
    print(f"✅ PM2 daemon: {'Matado' if pm2_killed else 'No encontrado'}")

    # 3. Esperar 1 segundo para estabilizar
    time.sleep(1)

    # 4. Verificar procesos restantes
    try:
        if os.name == 'nt':
            result = subprocess.run('tasklist', shell=True, capture_output=True, text=True)
            remaining = [l for l in result.stdout.split('\n') if any(t in l for t in ['python', 'node', 'pm2'])]
        else:
            result = subprocess.run('ps aux', shell=True, capture_output=True, text=True)
            remaining = [l for l in result.stdout.split('\n') if any(t in l for t in ['python', 'node', 'pm2'])]

        if remaining:
            print(f"⚠️  Procesos restantes: {len(remaining)}")
        else:
            print("✅ Todos los procesos detenidos.")
    except Exception as e:
        print(f"⚠️  Error verificando procesos: {e}")

    print("🔴 [AURA EMERGENCY STOP] Contención completada.")

if __name__ == '__main__':
    main()