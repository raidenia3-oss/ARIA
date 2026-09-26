"""Instalador de inicio automatico para AURA en Windows — Module 30.

Registra o elimina AURA del inicio automatico de Windows via el registro
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.

Uso:
    python install_autostart.py install [--exe PATH]
    python install_autostart.py uninstall
    python install_autostart.py status
    python install_autostart.py toggle
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

DEFAULT_APP_NAME = "AURA Assistant"
DEFAULT_EXE_NAME = "AURA_Assistant.exe"
REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
PYINSTALLER_EXE = str(Path(__file__).parent / "dist" / DEFAULT_EXE_NAME)
SCRIPT_EXE = str(Path(__file__).parent / "main_launcher.py")

IS_WINDOWS = sys.platform == "win32"


def _get_registry():
    if not IS_WINDOWS:
        raise OSError("Autostart registration only supported on Windows")
    import winreg
    return winreg


def _get_exe_path() -> str:
    """Resuelve la ruta al ejecutable o script de AURA."""
    if os.path.exists(PYINSTALLER_EXE):
        return PYINSTALLER_EXE
    if os.path.exists(SCRIPT_EXE):
        return f"{sys.executable} {SCRIPT_EXE}"
    return SCRIPT_EXE


def is_registered(app_name: str = DEFAULT_APP_NAME) -> bool:
    """Verifica si AURA esta registrado en el inicio automatico."""
    if not IS_WINDOWS:
        return False
    try:
        winreg = _get_registry()
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def get_registered_path(app_name: str = DEFAULT_APP_NAME) -> Optional[str]:
    """Obtiene la ruta registrada en el inicio automatico."""
    if not IS_WINDOWS:
        return None
    try:
        winreg = _get_registry()
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, app_name)
        winreg.CloseKey(key)
        return value
    except (FileNotFoundError, Exception):
        return None


def register(app_name: str = DEFAULT_APP_NAME, exe_path: Optional[str] = None) -> bool:
    """Registra AURA en el inicio automatico de Windows."""
    if not IS_WINDOWS:
        print("[red]El registro de inicio automatico solo es compatible con Windows.[/red]")
        return False

    exe_path = exe_path or _get_exe_path()
    if not os.path.exists(exe_path):
        print(f"[yellow]Advertencia: El archivo ejecutable no existe: {exe_path}[/yellow]")
        print("[yellow]Usando script Python como respaldo.[/yellow]")
        exe_path = f"{sys.executable} {SCRIPT_EXE}"

    try:
        winreg = _get_registry()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        print(f"[green][OK] AURA registrado en inicio automatico[/green]")
        print(f"  Nombre: {app_name}")
        print(f"  Ruta: {exe_path}")
        return True
    except Exception as exc:
        print(f"[red][FAIL] Error registrando en inicio automatico: {exc}[/red]")
        return False


def unregister(app_name: str = DEFAULT_APP_NAME) -> bool:
    """Elimina AURA del inicio automatico de Windows."""
    if not IS_WINDOWS:
        print("[red]El registro de inicio automatico solo es compatible con Windows.[/red]")
        return False

    try:
        winreg = _get_registry()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, app_name)
        winreg.CloseKey(key)
        print(f"[green][OK] AURA eliminado del inicio automatico[/green]")
        return True
    except FileNotFoundError:
        print(f"[yellow]AURA no esta registrado en inicio automatico.[/yellow]")
        return True
    except Exception as exc:
        print(f"[red][FAIL] Error eliminando del inicio automatico: {exc}[/red]")
        return False


def status(app_name: str = DEFAULT_APP_NAME) -> None:
    """Muestra el estado de registro de AURA en el inicio automatico."""
    if not IS_WINDOWS:
        print("[yellow]Windows-only feature. Current platform: {0}[/yellow]".format(sys.platform))
        return
    registered = is_registered(app_name)
    if registered:
        path = get_registered_path(app_name)
        print(f"[green][OK] Registrado[/green]")
        print(f"  Nombre: {app_name}")
        print(f"  Ruta: {path}")
    else:
        print(f"[yellow][FAIL] No registrado en inicio automatico[/yellow]")
        print(f"  Use: python install_autostart.py install")


def toggle(app_name: str = DEFAULT_APP_NAME, exe_path: Optional[str] = None) -> None:
    """Alterna el estado de registro en inicio automatico."""
    if is_registered(app_name):
        unregister(app_name)
    else:
        register(app_name, exe_path)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AURA Autostart Installer (Windows)")
    parser.add_argument("action", choices=["install", "uninstall", "status", "toggle"],
                        default="status", nargs="?",
                        help="Accion a ejecutar")
    parser.add_argument("--name", default=DEFAULT_APP_NAME, help="Nombre de registro")
    parser.add_argument("--exe", default=None, help="Ruta al ejecutable")

    args = parser.parse_args()

    if args.action == "install":
        register(args.name, args.exe)
    elif args.action == "uninstall":
        unregister(args.name)
    elif args.action == "status":
        status(args.name)
    elif args.action == "toggle":
        toggle(args.name, args.exe)


if __name__ == "__main__":
    main()
