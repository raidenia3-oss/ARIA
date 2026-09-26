"""
Script para abrir Chrome/Edge con puerto de depuración activo.
El usuario entra a RollerCoin y el módulo se conecta a esa ventana.
"""

import subprocess
import sys
import os

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
DEBUG_PORT = 9222
USER_DATA_DIR = os.path.expandvars(r"%TEMP%\rollercoin_chrome_profile")


def launch():
    chrome = None
    for path in CHROME_PATHS:
        if os.path.exists(path):
            chrome = path
            break

    if not chrome:
        print("❌ Chrome/Edge no encontrado")
        sys.exit(1)

    cmd = [
        chrome,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://rollercoin.com/game",
    ]

    print("Abriendo Chrome con debug activo...")
    print(f"   Puerto de debug: {DEBUG_PORT}")
    print(f"   Perfil: {USER_DATA_DIR}")
    print()
    print("INSTRUCCIONES:")
    print("1. El navegador se abrirá en RollerCoin")
    print("2. Si pide login, inicia sesión normalmente")
    print("3. Una vez dentro del juego, ejecuta:")
    print("   python AME_Core/rollercoin/main_v2.py")
    print()

    subprocess.Popen(cmd)
    print("Chrome iniciado")


if __name__ == "__main__":
    launch()
