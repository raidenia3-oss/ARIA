#!/usr/bin/env python3
"""
diagnostic_termux.py: Script para diagnosticar y solucionar problemas de conexión con Termux.
"""

import subprocess
import time
import os

def run_command(command):
    """Ejecuta un comando y devuelve su salida."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout al ejecutar el comando"

def check_ssh_connection():
    """Verifica la conexión SSH a Termux."""
    print("Verificando conexión SSH a Termux...")
    returncode, stdout, stderr = run_command('ssh -p 8022 u0_a1167@192.168.3.14 "echo OK && whoami"')

    if returncode == 0:
        print("✅ Conexión SSH exitosa.")
        print(f"Salida: {stdout}")
        return True
    else:
        print("❌ No se pudo establecer conexión SSH.")
        print(f"Error: {stderr}")
        return False

def check_termux_services():
    """Verifica si los servicios necesarios están corriendo en Termux."""
    print("\nVerificando servicios en Termux...")

    # Intentar conectar y ejecutar comandos para verificar servicios
    commands = [
        'ssh -p 8022 u0_a1167@192.168.3.14 "test -f ~/auto_connect.sh && echo \'✅ auto_connect.sh existe\'"',
        'ssh -p 8022 u0_a1167@192.168.3.14 "ps aux | grep -i \'servidor.py\' | grep -v grep && echo \'✅ servidor.py está corriendo\'"',
        'ssh -p 8022 u0_a1167@192.168.3.14 "ss -tulnp | grep 8022 && echo \'✅ SSH está escuchando en el puerto 8022\'"',
    ]

    for cmd in commands:
        returncode, stdout, stderr = run_command(cmd)
        if returncode == 0 and stdout:
            print(stdout)
        else:
            print(f"❌ {cmd.split()[-1]} no parece estar disponible o no se pudo verificar.")

def check_network_connectivity():
    """Verifica la conectividad de red con el dispositivo Termux."""
    print("\nVerificando conectividad de red...")

    # Intenta pingear la dirección IP de Termux
    returncode, stdout, stderr = run_command('ping -n 4 192.168.3.14')

    if returncode == 0:
        print("✅ El dispositivo en 192.168.3.14 está respondiendo al ping.")
    else:
        print("❌ No se puede pingear 192.168.3.14.")
        print(f"Error: {stderr}")

def start_ssh_service():
    """Intenta iniciar el servicio SSH en Termux si es posible."""
    print("\nIntentando iniciar el servicio SSH en Termux...")

    # Este comando es solo para intentar conectar y ejecutar el servicio SSH
    command = 'ssh -p 8022 u0_a1167@192.168.3.14 "pkg install openssh -y && sshd"'
    returncode, stdout, stderr = run_command(command)

    if returncode == 0:
        print("✅ Servicio SSH iniciado en Termux.")
    else:
        print("❌ No se pudo iniciar el servicio SSH en Termux.")
        print(f"Error: {stderr}")

def main():
    """Función principal del script."""
    print("=" * 50)
    print("DIAGNÓSTICO DE CONEXIÓN CON TERMUX")
    print("=" * 50)

    # Verificar conectividad de red
    check_network_connectivity()

    # Verificar conexión SSH
    ssh_success = check_ssh_connection()

    if ssh_success:
        # Si la conexión SSH es exitosa, verificar servicios
        check_termux_services()
    else:
        # Si no hay conexión SSH, intentar iniciar el servicio SSH
        start_ssh_service()

    print("\n" + "=" * 50)
    print("DIAGNÓSTICO COMPLETADO")
    print("=" * 50)

if __name__ == "__main__":
    main()