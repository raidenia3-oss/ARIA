"""
Script para registrar AURA como proceso de inicio automático en Windows.
Este script crea un acceso directo en la carpeta de inicio del usuario para ejecutar AURA de forma silenciosa.
"""

import os
import sys
import ctypes
import winreg
import subprocess
import shutil
from pathlib import Path

# Ruta base del proyecto
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
AURA_DIR = BASE_DIR / "AURA_Core"
SETUP_DIR = BASE_DIR / "Setup"

# Ruta a PM2 (asumiendo que está instalado globalmente)
PM2_PATH = shutil.which("pm2")

# Ruta al script principal de AURA
AURA_SCRIPT = AURA_DIR / "crash_overseer.py"

# Ruta a la carpeta de inicio del usuario
STARTUP_FOLDER = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

# Ruta al archivo de acceso directo (.lnk)
LNK_FILE = STARTUP_FOLDER / "AURA Stealth Mode.lnk"

def create_shortcut(target_path, shortcut_path, description="AURA Stealth Mode"):
    """
    Crea un acceso directo (.lnk) en Windows.
    """
    try:
        # Definir la estructura del acceso directo
        shell = ctypes.windll.shell32
        shell32 = ctypes.windll.shell32

        # Crear el acceso directo
        path = ctypes.c_wchar_p(str(shortcut_path))
        target = ctypes.c_wchar_p(str(target_path))
        description = ctypes.c_wchar_p(description)

        # Parámetros para el acceso directo
        params = ctypes.c_wchar_p("/c pm2 resurrect && pm2 start crash_overseer.py --silent")

        # Crear el acceso directo
        shell.SHCreateShortcut(
            path,
            0,  # No mostrar icono
            0,  # No mostrar ventana
            target,
            None,  # No usar working directory
            params,
            description,
            None,  # No usar icono personalizado
            None,  # No usar hotkey
            None,  # No usar comentarios
            0,  # No usar flags especiales
            None,  # No usar extra data
            None  # No usar run arguments
        )

        print(f"✅ Acceso directo creado en: {shortcut_path}")
        return True
    except Exception as e:
        print(f"❌ Error creando acceso directo: {e}")
        return False

def register_autoboot():
    """
    Registra AURA para que se inicie automáticamente con Windows.
    """
    try:
        # Verificar que PM2 esté instalado
        if not PM2_PATH:
            print("❌ PM2 no está instalado. Instálalo con: npm install pm2 -g")
            return False

        # Verificar que el script de AURA exista
        if not AURA_SCRIPT.exists():
            print(f"❌ Script de AURA no encontrado: {AURA_SCRIPT}")
            return False

        # Crear la carpeta de inicio si no existe
        STARTUP_FOLDER.mkdir(parents=True, exist_ok=True)

        # Crear el acceso directo
        if create_shortcut(f"{PM2_PATH} start {AURA_SCRIPT}", LNK_FILE):
            print(f"✅ AURA registrado para iniciar automáticamente con Windows.")
            print(f"📌 Acceso directo creado en: {LNK_FILE}")
            print(f"🔍 Para verificar, abre 'shell:startup' en la barra de direcciones de Windows.")
            return True
        else:
            print("❌ No se pudo crear el acceso directo.")
            return False
    except Exception as e:
        print(f"❌ Error registrando AURA para inicio automático: {e}")
        return False

def verify_pm2_installed():
    """
    Verifica si PM2 está instalado globalmente.
    """
    try:
        result = subprocess.run([PM2_PATH, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PM2 está instalado (versión: {result.stdout.strip()})")
            return True
        else:
            print("❌ PM2 no está instalado o no es accesible.")
            return False
    except Exception as e:
        print(f"❌ Error verificando PM2: {e}")
        return False

def install_pm2():
    """
    Intenta instalar PM2 globalmente.
    """
    try:
        print("🔧 Intentando instalar PM2 globalmente...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pm2"], check=True)
        print("✅ PM2 instalado correctamente.")
        return True
    except Exception as e:
        print(f"❌ Error instalando PM2: {e}")
        return False

def main():
    """
    Función principal del script.
    """
    print("🚀 Configurando arranque automático de AURA en Windows (Stealth Mode)...")

    # Verificar si PM2 está instalado
    if not verify_pm2_installed():
        # Intentar instalar PM2
        if not install_pm2():
            print("❌ No se pudo instalar PM2. Asegúrate de tener permisos de administrador.")
            return

    # Registrar AURA para inicio automático
    if register_autoboot():
        print("\n🎉 Configuración completada con éxito.")
        print("📌 Instrucciones para verificar:")
        print("1. Presiona Win + R y escribe 'shell:startup' para abrir la carpeta de inicio.")
        print("2. Verifica que el acceso directo 'AURA Stealth Mode.lnk' esté presente.")
        print("3. Reinicia tu computadora para probar el arranque automático.")
    else:
        print("\n❌ Configuración fallida. Verifica los permisos y la instalación de PM2.")

if __name__ == "__main__":
    # Verificar permisos de administrador
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("⚠️ Este script requiere permisos de administrador para registrar el acceso directo.")
        print("🔧 Ejecutando con elevación de privilegios...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        main()