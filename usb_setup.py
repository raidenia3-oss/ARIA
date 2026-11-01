# -*- coding: utf-8 -*-
"""Setup de 1 vez: convierte el USB en el 'cerebro portatil' de ARIA.

Detecta el USB, crea la estructura, copia el modelo GGUF al USB y escribe el
lanzador aria_usb_launcher.py. Despues ARIA arranca desde el USB (modelo + espacio
de trabajo en el USB), liberando disco y manteniendo el cerebro fuera de la PC.
Colocar en la RAIZ del repo (junto a ARIA_APP). Uso: python usb_setup.py
"""
import os
import sys
import glob
import string
import ctypes
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "ARIA_APP")
DRIVE_REMOVABLE = 2


def usb_drives():
    out = []
    try:
        bm = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return out
    for i, l in enumerate(string.ascii_uppercase):
        if (bm >> i) & 1:
            root = "%s:\\" % l
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == DRIVE_REMOVABLE:
                    out.append(root)
            except Exception:
                pass
    return out


def main():
    usbs = usb_drives()
    if not usbs:
        print("No detecto ningun USB/extraible. Conectalo y reintenta.")
        return 1
    usb = usbs[0]
    print("USB detectado:", usb)
    base = os.path.join(usb, "ARIA")
    for d in ("models", "work", "data"):
        os.makedirs(os.path.join(base, d), exist_ok=True)

    # copiar modelo(s) GGUF al USB
    modelos = glob.glob(os.path.join(APP, "models", "*.gguf"))
    copiados = []
    for m in modelos:
        dst = os.path.join(base, "models", os.path.basename(m))
        if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(m)):
            print("copiando", os.path.basename(m), "(%.0f MB)..." % (os.path.getsize(m) / 1e6))
            shutil.copy2(m, dst)
        copiados.append(os.path.basename(m))
    if not copiados:
        print("AVISO: no encontre modelo .gguf en ARIA_APP/models (el lanzador usara el que haya).")

    # escribir lanzador
    lanz = os.path.join(ROOT, "aria_usb_launcher.py")
    with open(lanz, "w", encoding="utf-8") as f:
        f.write(_LAUNCHER)
    bat = os.path.join(ROOT, "ARIA_USB.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write('@echo off\r\n"%~dp0.venv\\Scripts\\python.exe" "%~dp0aria_usb_launcher.py"\r\npause\r\n')

    print("\nLISTO.")
    print("  Modelo(s) en USB:", ", ".join(copiados) or "(ninguno)")
    print("  Lanzador: ARIA_USB.bat  (doble clic para arrancar ARIA desde el USB)")
    print("  Ya puedes borrar el modelo de ARIA_APP/models para liberar disco (opcional).")
    return 0


_LAUNCHER = '''# -*- coding: utf-8 -*-
"""Lanza ARIA usando el modelo y datos del USB (auto-detecta la unidad)."""
import os, sys, glob, string, ctypes

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, "ARIA_APP")


def find_usb():
    try:
        bm = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return None
    for i, l in enumerate(string.ascii_uppercase):
        if (bm >> i) & 1:
            root = "%s:\\\\" % l
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 2:
                    if glob.glob(os.path.join(root, "ARIA", "models", "*.gguf")):
                        return os.path.join(root, "ARIA")
            except Exception:
                pass
    return None


u = find_usb()
if u:
    m = glob.glob(os.path.join(u, "models", "*.gguf"))
    if m:
        os.environ["ARIA_LLM_MODEL"] = m[0]
    os.environ["ARIA_FS_ROOTS"] = os.path.join(u, "work")
    print("[USB] ARIA desde:", u)
else:
    print("[USB] no detectado; uso el modelo local si existe.")

sys.path.insert(0, APP)
os.chdir(APP)
import aria_main
aria_main.main()
'''


if __name__ == "__main__":
    sys.exit(main())
