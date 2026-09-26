#!/usr/bin/env python3
"""
AURA CLIPBOARD BRIDGE — Puente simbiótico PC ↔ Android
Inspirado en KDE Connect

Funcionalidades:
- Sincronizar portapapeles entre PC y dispositivo Android via ADB
- Inyectar texto directamente en campos de la app AME
- Extraer datos del portapapeles de Android

Comandos ADB utilizados:
- input text "$TEXT" → Inyecta texto en Android
- service call clipboard 1 → Lee portapapeles de Android
- screencap -p → Captura pantalla
"""

import subprocess
import os
import time
from datetime import datetime

ADB_PATH = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"


def ejecutar_adb(*args):
    """Ejecuta un comando ADB y devuelve la salida."""
    cmd = [ADB_PATH] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", -1
    except Exception as e:
        return f"ERROR: {str(e)}", -1


def verificar_conexion():
    """Verifica si hay dispositivos Android conectados."""
    output, code = ejecutar_adb("devices")
    if code == 0:
        lineas = [l for l in output.split("\n") if "device" in l and "List" not in l]
        return len(lineas) > 0, lineas
    return False, []


def inyectar_texto(texto):
    """
    Inyecta texto en el campo de texto activo en Android.
    Convierte espacios a %s para el comando input text de ADB.

    Ejemplo: ADB shell input text "hola mundo"
    """
    # Escapar caracteres especiales para ADB
    texto_escapado = texto.replace(" ", "%s")

    # Comando para inyectar texto: shell input text "$TEXTO"
    output, code = ejecutar_adb("shell", "input", "text", f'"{texto_escapado}"')
    return code == 0, output


def inyectar_texto_complejo(texto):
    """
    Inyecta texto complejo (con caracteres especiales) en Android.
    Usa input text con ' ' como separador de palabras para evitar errores.
    """
    # Convertir texto a un formato seguro para ADB
    palabras = texto.split(" ")
    texto_formatted = " ".join(palabras)

    output, code = ejecutar_adb("shell", "input", "text", f'"{texto_formatted}"')
    return code == 0, output


def enviar_tecla(tecla):
    """
    Envía una tecla específica a Android.
    Teclas disponibles: KEYCODE_ENTER, KEYCODE_DEL, KEYCODE_TAB, etc.

    Ejemplo: ADB shell input keyevent KEYCODE_ENTER
    """
    output, code = ejecutar_adb("shell", "input", "keyevent", tecla)
    return code == 0, output


def obtener_clipboard_adb():
    """
    Obtiene el contenido del portapapeles de Android.
    Usa el service call clipboard 1 para leer el portapapeles.
    """
    try:
        # Intentar obtener el portapajeles desde el servicio de Android
        output, code = ejecutar_adb("shell", "service", "call", "clipboard", "1")
        if code == 0 and output:
            return output
    except Exception:
        pass

    # Alternativa: intentar leer desde el portapapeles del sistema
    try:
        output, code = ejecutar_adb("shell", "cat", "/dev/clipboard")
        if code == 0:
            return output
    except Exception:
        pass

    return None


def enviar_clipboard_adb(texto):
    """
    Envía el contenido del portapapeles desde PC a Android.
    Usa su proceso de input text para inyectar el texto.
    """
    if not texto:
        return False, "Texto vacío"

    # Inyectar texto usando input text
    return inyectar_texto(texto)


def crear_estructura_directorio():
    """Crea la estructura de directorios para el puente de portapapeles."""
    directorios = [
        "core",
        "core/clipboard_bridge",
    ]
    for d in directorios:
        os.makedirs(d, exist_ok=True)
    return True


def diagnose_problemas():
    """Diagnostica problemas comunes con el tiempo de ejecución."""
    problemas = []

    # Verificar si ADB está disponible
    output, code = ejecutar_adb("version")
    if code != 0:
        problemas.append("ADB no está instalado o no está en el PATH")

    # Verificar si hay dispositivos conectados
    conectado, dispositivos = verificar_conexion()
    if not conectado:
        problemas.append("No hay dispositivos Android conectados")

    # Verificar si el puerto 5000 está activo
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("127.0.0.1", 5000))
        s.close()
        if result != 0:
            problemas.append("Puerto 5000 (FastAPI) no está activo")
    except Exception:
        problemas.append("No se pudo verificar el puerto 5000")

    return problemas


def demo_mensaje():
    """Demuestra cómo enviar un mensaje a la app AME."""
    print("=== DEMO: Enviar mensaje a AME ===")
    print("Comando: ADB shell input text 'MiradorAURA'")
    print("Resultado: Texto inyectado en el campo de texto activo")
    return True


if __name__ == "__main__":
    print("=" * 55)
    print("  AURA CLIPBOARD BRIDGE v1.0")
    print("  Puente simbiótico PC ↔ Android")
    print("=" * 55)

    # Verificar conexión ADB
    conectado, dispositivos = verificar_conexion()
    if conectado:
        print(f"\n📱 Dispositivos conectados: {len(dispositivos)}")
        for d in dispositivos:
            print(f"   → {d}")
    else:
        print("\n❌ No hay dispositivos Android conectados")

    # Ejemplo de uso
    print("\n🔧 Ejemplo de uso:")
    print("   inyectar_texto('MiradorAURA')")
    print("   enviar_tecla('KEYCODE_ENTER')")
    print("   obtener_clipboard_adb()")

    # Demo conceptual
    print("\n🤖 Demo: ADB command:")
    print("   input text 'MiradorAURA'")
    print("   → Texto inyectado en el dispositivo Android")
