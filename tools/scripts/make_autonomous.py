#!/usr/bin/env python3
"""make_autonomous.py - Instala AURA como servicio autónomo invisible en Windows."""

from __future__ import annotations

import os
import sys
import shutil
import ctypes
import ctypes.wintypes
import winreg
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_LAUNCHER = PROJECT_ROOT / "main_launcher.py"
PYTHON_EXECUTABLE = sys.executable
STARTUP_FOLDER = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
VBS_NAME = "AURA_Autonomous.vbs"
VBS_PATH = STARTUP_FOLDER / VBS_NAME


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def create_vbs() -> None:
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python main_launcher.py", 0, False
Set WshShell = Nothing
'''
    VBS_PATH.write_text(vbs_content, encoding="utf-8")


def install_vbs() -> None:
    create_vbs()
    print(f"[OK] Startup VBS creado en: {VBS_PATH}")


def uninstall_vbs() -> None:
    if VBS_PATH.exists():
        VBS_PATH.unlink()
        print(f"[OK] Startup VBS eliminado: {VBS_PATH}")
    else:
        print("[INFO] No hay VBS de AURA en Startup.")


def install_task_scheduler() -> None:
    task_name = "AURA_Autonomous"
    python_dir = str(Path(PYTHON_EXECUTABLE).parent)
    main_launcher_abs = str(MAIN_LAUNCHER.resolve())
    xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>"{PYTHON_EXECUTABLE}"</Command>
      <Arguments>"{main_launcher_abs}"</Arguments>
      <WorkingDirectory>{PROJECT_ROOT}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'''
    xml_path = PROJECT_ROOT / "aura_task.xml"
    xml_path.write_text(xml, encoding="utf-16")
    print(f"[OK] XML de tarea exportado en: {xml_path}")
    print("    Para registrarla manualmente ejecutá como Administrador:")
    print(f'    schtasks /create /tn "{task_name}" /xml "{xml_path}" /f')


def run_autonomous() -> None:
    print("========================================")
    print("  AURA AUTONOMOUS INSTALLER")
    print("========================================")
    print(f"Proyecto:   {PROJECT_ROOT}")
    print(f"Launcher:   {MAIN_LAUNCHER}")
    print(f"Python:     {PYTHON_EXECUTABLE}")
    print(f"Startup:    {STARTUP_FOLDER}")
    print()

    if not MAIN_LAUNCHER.exists():
        print(f"[FAIL] No se encontró main_launcher.py en {MAIN_LAUNCHER}")
        sys.exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else "vbs"

    if mode == "vbs":
        install_vbs()
        print("\nAURA se iniciará invisible al encender la PC.")
        print("Para desinstalar: python scripts/make_autonomous.py uninstall")
    elif mode == "task":
        install_task_scheduler()
        if is_admin():
            print("\nRegistrando tarea programada...")
            subprocess.run(
                [
                    "schtasks",
                    "/create",
                    "/tn",
                    "AURA_Autonomous",
                    "/xml",
                    str((PROJECT_ROOT / "aura_task.xml").resolve()),
                    "/f",
                ],
                check=True,
            )
            print("[OK] Tarea programada registrada.")
        else:
            print("[WARN] Ejecutá este script como Administrador para registrar la tarea.")
    elif mode == "uninstall":
        uninstall_vbs()
    else:
        print("Modos soportados: vbs | task | uninstall")
        sys.exit(1)


if __name__ == "__main__":
    run_autonomous()
