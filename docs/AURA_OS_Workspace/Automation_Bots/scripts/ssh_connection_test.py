#!/usr/bin/env python3
"""
Script para probar la conexión SSH entre la PC y Termux.
"""

import subprocess
import os
import sys

# Configuración
TERMUX_IP = "192.168.3.14"
TERMUX_USER = "u0_a1167"
TERMUX_PORT = "8022"
SSH_KEY_PATH = os.path.expanduser("~/.ssh/id_rsa")

def test_ssh_connection():
    """Prueba la conexión SSH a Termux."""
    print(f"🔍 Probando conexión SSH a {TERMUX_USER}@{TERMUX_IP}:{TERMUX_PORT}")
    print("=" * 50)

    # Verificar si existe la clave SSH
    print("1. Verificando clave SSH...")
    if not os.path.exists(SSH_KEY_PATH):
        print(f"   ❌ Error: No se encontró la clave SSH en {SSH_KEY_PATH}")
        return False
    print(f"   ✅ Clave SSH encontrada en {SSH_KEY_PATH}")

    # Verificar permisos de la clave SSH
    print("2. Verificando permisos de la clave SSH...")
    import stat
    mode = os.stat(SSH_KEY_PATH).st_mode
    permissions = stat.filemode(mode)
    print(f"   📋 Permisos actuales: {permissions}")

    if permissions != '-rw-------':
        print("   ⚠️  Advertencia: Los permisos no son 600. Recomendado:")
        print("      chmod 600 ~/.ssh/id_rsa")
    else:
        print("   ✅ Permisos correctos (600)")

    # Probar conexión SSH
    print("3. Probando conexión SSH...")
    try:
        command = f"ssh -p {TERMUX_PORT} -i {SSH_KEY_PATH} -o BatchMode=yes -o ConnectTimeout=5 {TERMUX_USER}@{TERMUX_IP} 'echo Connected'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)

        if result.returncode == 0 and "Connected" in result.stdout:
            print("   ✅ ¡Conexión SSH exitosa!")
            print(f"   📡 Respuesta del servidor: {result.stdout.strip()}")
            return True
        else:
            print(f"   ❌ Error al conectar a SSH")
            print(f"   📋 Código de retorno: {result.returncode}")
            print(f"   📋 Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("   ❌ Tiempo de espera agotado al intentar conectar a SSH.")
        print("      Verifica que el servicio SSH esté corriendo en Termux.")
        return False
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")
        return False

def check_ssh_key_permissions():
    """Verifica los permisos de la clave SSH."""
    if os.path.exists(SSH_KEY_PATH):
        import stat
        mode = os.stat(SSH_KEY_PATH).st_mode
        permissions = stat.filemode(mode)
        print(f"🔒 Permisos de la clave SSH: {permissions}")

        if permissions != '-rw-------':
            print("⚠️  Advertencia: Los permisos de la clave SSH no son 600.")
            print("   Ejecuta: chmod 600 ~/.ssh/id_rsa")

def main():
    print("🚀 Iniciando prueba de conexión SSH a Termux")
    print("=" * 50)

    # Verificar permisos de la clave SSH
    check_ssh_key_permissions()

    # Probar conexión SSH
    if test_ssh_connection():
        print("\n🎉 ¡Conexión SSH validada con éxito!")
        print("Puedes proceder a la Fase B: Comunicación Base SSH.")
    else:
        print("\n❌ No se pudo validar la conexión SSH.")
        print("\n📋 Pasos para resolver:")
        print("1. Verifica que el servicio SSH esté corriendo en Termux:")
        print("   pkg install openssh")
        print("   sshd")
        print("2. Verifica que la IP y el puerto sean correctos.")
        print(f"   IP: {TERMUX_IP}, Puerto: {TERMUX_PORT}")
        print("3. Verifica que los permisos de la clave SSH sean correctos.")
        print("4. Verifica que ambos dispositivos estén en la misma red.")
        print("5. Verifica que la clave pública esté en Termux:")
        print("   cat ~/.ssh/authorized_keys")

if __name__ == "__main__":
    main()