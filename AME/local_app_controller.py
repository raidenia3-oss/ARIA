"""
Local App Controller
====================
Controla aplicaciones locales del sistema: Android Studio, OBSidian, Godot,
Unity Hub, Python, Jan, etc.

Funcionalidades:
  - Detectar apps instaladas
  - Lanzar/cerrar apps
  - Ejecutar scripts Python
  - Ejecutar comandos de consola
  - Leer/escribir archivos de configuracion
  - Controlar procesos en ejecucion

Variables de entorno:
  APPS_ANDROID_STUDIO  - Ruta a Android Studio (default: C:/Program Files/Android/Android Studio/bin/studio64.exe)
  APPS_OBSIDIAN        - Ruta a Obsidian (default: LOCALAPPDATA/Programs/Obsidian/Obsidian.exe)
  APPS_OBS             - Ruta a OBS Studio (default: C:/Program Files/OBS Studio/bin/64bit/obs64.exe)
  APPS_GODOT           - Ruta a Godot (default: LOCALAPPDATA/Programs/Godot/godot.exe)
  APPS_UNITY_HUB       - Ruta a Unity Hub (default: C:/Program Files/Unity Hub/Unity Hub.exe)
  APPS_PYTHON          - Ruta a Python (default: python)
  APPS_JAN             - Ruta a Jan (default: LOCALAPPDATA/Programs/jan/Jan.exe)
  APPS_TERMINAL        - Terminal preferida (default: powershell)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class LocalAppController:
    """Controlador de aplicaciones locales de AURA."""

    def __init__(self) -> None:
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.apps: Dict[str, Dict[str, Any]] = self._discover_apps()

    def _discover_apps(self) -> Dict[str, Dict[str, Any]]:
        """Detecta todas las apps instaladas."""
        discovered: Dict[str, Dict[str, Any]] = {}
        localappdata = os.environ.get("LOCALAPPDATA", "")
        programfiles = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        programfiles_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        start_menu_programs = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs"
        )

        def _resolve_shortcut(lnk_path: str) -> str:
            """Resolve .lnk shortcut target using PowerShell (no win32com dependency)."""
            try:
                ps = (
                    f'(New-Object -ComObject WScript.Shell).CreateShortcut('
                    f'"{lnk_path}").Targetpath'
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=5
                )
                target = result.stdout.strip()
                if target:
                    return target
            except Exception:
                pass
            return ""

        godot_lnk = os.path.join(start_menu_programs, "Godot_v4.lnk")
        godot_from_lnk = _resolve_shortcut(godot_lnk) if os.path.exists(godot_lnk) else ""

        candidates = {
            "android_studio": [
                os.getenv("APPS_ANDROID_STUDIO", ""),
                os.path.join(programfiles, "Android", "Android Studio", "bin", "studio64.exe"),
                os.path.join(programfiles_x86, "Android", "Android Studio", "bin", "studio64.exe"),
            ],
            "vs_code": [
                os.getenv("APPS_VS_CODE", ""),
                os.path.join(localappdata, "Programs", "Microsoft VS Code", "Code.exe"),
                os.path.join(programfiles, "Microsoft VS Code", "Code.exe"),
                os.path.join(programfiles_x86, "Microsoft VS Code", "Code.exe"),
            ],
            "antigravity": [
                os.getenv("APPS_ANTIGRAVITY", ""),
                os.path.join(localappdata, "Programs", "Antigravity IDE", "antigravity.exe"),
            ],
            "obsidian": [
                os.getenv("APPS_OBSIDIAN", ""),
                os.path.join(localappdata, "Programs", "Obsidian", "Obsidian.exe"),
                os.path.join(localappdata, "Obsidian", "Obsidian.exe"),
            ],
            "obs": [
                os.getenv("APPS_OBS", ""),
                os.path.join(programfiles, "OBS Studio", "bin", "64bit", "obs64.exe"),
                os.path.join(programfiles_x86, "OBS Studio", "bin", "64bit", "obs64.exe"),
            ],
            "godot": [
                os.getenv("APPS_GODOT", ""),
                godot_from_lnk,
                os.path.join(localappdata, "Programs", "Godot", "godot.exe"),
                os.path.join(localappdata, "Godot", "Godot.exe"),
                os.path.join(programfiles, "Godot", "godot.exe"),
                os.path.join(programfiles_x86, "Godot", "godot.exe"),
                shutil.which("godot") or "",
                os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Godot_v4-stable_win64.exe"),
                os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Godot_v4.6-stable_win64.exe"),
                os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Godot", "godot.exe"),
                os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "Godot_v4.6-stable_win64", "Godot.exe"),
            ],
            "unity_hub": [
                os.getenv("APPS_UNITY_HUB", ""),
                os.path.join(programfiles, "Unity Hub", "Unity Hub.exe"),
                os.path.join(programfiles_x86, "Unity Hub", "Unity Hub.exe"),
            ],
            "python": [
                os.getenv("APPS_PYTHON", ""),
                shutil.which("python") or "",
                shutil.which("python3") or "",
                os.path.join(localappdata, "Programs", "Python", "Python311", "python.exe"),
                os.path.join(localappdata, "Programs", "Python", "Python310", "python.exe"),
            ],
            "jan": [
                os.getenv("APPS_JAN", ""),
                os.path.join(localappdata, "Programs", "jan", "Jan.exe"),
            ],
        }

        for app_name, paths in candidates.items():
            exe_path = ""
            for p in paths:
                if p and Path(p).is_file():
                    exe_path = str(Path(p).resolve())
                    break
            discovered[app_name] = {
                "name": app_name,
                "installed": bool(exe_path),
                "path": exe_path,
                "running": False,
            }

        return discovered

    def is_running(self, app_name: str) -> bool:
        """Verifica si una app esta corriendo."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self._get_process_name(app_name)}"],
                capture_output=True, text=True, timeout=5
            )
            return app_name in result.stdout.lower() or self._get_process_name(app_name).lower() in result.stdout.lower()
        except Exception:
            return False

    def _get_process_name(self, app_name: str) -> str:
        """Nombre del proceso en Windows."""
        process_map = {
            "android_studio": "studio64.exe",
            "vs_code": "Code.exe",
            "antigravity": "antigravity.exe",
            "obsidian": "Obsidian.exe",
            "obs": "obs64.exe",
            "godot": "godot.exe",
            "unity_hub": "Unity Hub.exe",
            "python": "python.exe",
            "jan": "Jan.exe",
        }
        return process_map.get(app_name, f"{app_name}.exe")

    def launch(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Lanza una aplicacion local."""
        if app_name not in self.apps:
            return {"ok": False, "error": f"App desconocida: {app_name}"}

        app = self.apps[app_name]
        if not app["installed"]:
            return {"ok": False, "error": f"{app_name} no esta instalada"}

        if self.is_running(app_name):
            return {"ok": True, "message": f"{app_name} ya esta corriendo", "running": True}

        try:
            cmd = [app["path"]] + (args or [])
            if self.is_windows:
                subprocess.Popen(cmd, shell=False, creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen(cmd, shell=False, start_new_session=True)

            time.sleep(1)
            app["running"] = self.is_running(app_name)
            return {
                "ok": True,
                "message": f"{app_name} lanzada correctamente",
                "running": app["running"],
                "path": app["path"],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def kill(self, app_name: str) -> Dict[str, Any]:
        """Cierra una aplicacion."""
        if app_name not in self.apps:
            return {"ok": False, "error": f"App desconocida: {app_name}"}

        proc_name = self._get_process_name(app_name)
        try:
            subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, timeout=5)
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True, text=True, timeout=5)
            self.apps[app_name]["running"] = False
            return {"ok": True, "message": f"{app_name} cerrada"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def execute_python(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Ejecuta un script Python en el sistema local."""
        python_exe = self.apps.get("python", {}).get("path", "python")
        if not python_exe:
            return {"ok": False, "error": "Python no encontrado"}

        script = Path(script_path)
        if not script.is_file():
            return {"ok": False, "error": f"Script no encontrado: {script_path}"}

        try:
            cmd = [python_exe, str(script)] + (args or [])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(script.parent))
            return {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-2000:],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Timeout: script tardo mas de 5 minutos"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def run_command(self, command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        """Ejecuta un comando de consola."""
        try:
            if self.is_windows:
                result = subprocess.run(
                    ["cmd", "/C", command],
                    capture_output=True, text=True, timeout=60, cwd=cwd
                )
            else:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
                )
            return {
                "ok": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-2000:],
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Lee un archivo local."""
        try:
            path = Path(file_path)
            if not path.is_file():
                return {"ok": False, "error": f"Archivo no encontrado: {file_path}"}
            content = path.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "content": content[-8000:], "path": str(path)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Escribe un archivo local."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"ok": True, "path": str(path), "bytes": len(content)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def list_directory(self, dir_path: str) -> Dict[str, Any]:
        """Lista archivos de un directorio."""
        try:
            path = Path(dir_path)
            if not path.is_dir():
                return {"ok": False, "error": f"Directorio no encontrado: {dir_path}"}
            items = []
            for item in sorted(path.iterdir()):
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return {"ok": True, "items": items[:100], "total": len(items)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_obsidian_vault(self, vault_path: str) -> Dict[str, Any]:
        """Abre un vault de Obsidian."""
        if not self.apps.get("obsidian", {}).get("installed"):
            return {"ok": False, "error": "Obsidian no esta instalado"}

        vault = Path(vault_path)
        if not vault.is_dir():
            return {"ok": False, "error": f"Vault no encontrado: {vault_path}"}

        try:
            subprocess.Popen([self.apps["obsidian"]["path"], str(vault)],
                           creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": f"Obsidian vault abierto: {vault_path}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def godot_run_project(self, project_path: str) -> Dict[str, Any]:
        """Ejecuta un proyecto de Godot."""
        godot_exe = self.apps.get("godot", {}).get("path")
        if not godot_exe:
            return {"ok": False, "error": "Godot no esta instalado"}

        project = Path(project_path)
        if not project.is_dir():
            return {"ok": False, "error": f"Proyecto no encontrado: {project_path}"}

        project_godot = project / "project.godot"
        if not project_godot.is_file():
            return {"ok": False, "error": f"No es un proyecto Godot valido: {project_path}"}

        try:
            subprocess.Popen([godot_exe, "--path", str(project), "--verbose"],
                           creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": f"Godot ejecutando: {project_path}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def android_studio_open_project(self, project_path: str = "") -> Dict[str, Any]:
        """Abre Android Studio (con proyecto opcional)."""
        studio = self.apps.get("android_studio", {})
        if not studio.get("installed"):
            return {"ok": False, "error": "Android Studio no esta instalado"}

        try:
            cmd = [studio["path"]]
            if project_path:
                cmd.append(str(project_path))
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": "Android Studio abierto",
                    "path": studio["path"], "project": project_path or None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def android_studio_run_gradle(self, project_path: str, task: str = "assembleDebug") -> Dict[str, Any]:
        """Ejecuta un comando Gradle en un proyecto Android."""
        if not self.apps.get("android_studio", {}).get("installed"):
            return {"ok": False, "error": "Android Studio no instalado"}

        gradlew = pathlib.Path(project_path) / "gradlew"
        if not gradlew.is_file():
            return {"ok": False, "error": f"gradlew no encontrado en: {project_path}"}

        try:
            cmd = [str(gradlew), task]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=600, cwd=project_path)
            return {"ok": result.returncode == 0, "task": task,
                    "returncode": result.returncode,
                    "stdout": result.stdout[-4000:],
                    "stderr": result.stderr[-2000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Timeout: Gradle tardo mas de 10 minutos"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def android_studio_get_projects(self, base_dir: str = "") -> Dict[str, Any]:
        """Busca proyectos Android Studio en un directorio."""
        import glob as _glob
        base = pathlib.Path(base_dir) if base_dir else pathlib.Path.home() / "AndroidProjects"
        if not base.is_dir():
            return {"ok": False, "error": f"Directorio no encontrado: {base}"}

        projects = []
        for manifest in base.rglob("AndroidManifest.xml"):
            proj_dir = manifest.parent
            has_gradle = (proj_dir / "build.gradle").is_file() or (proj_dir / "build.gradle.kts").is_file()
            if has_gradle:
                projects.append({
                    "name": proj_dir.name,
                    "path": str(proj_dir),
                    "has_gradlew": (proj_dir / "gradlew").is_file(),
                })
        return {"ok": True, "projects": projects[:50], "total": len(projects)}

    def unity_open_project(self, project_path: str) -> Dict[str, Any]:
        """Abre un proyecto de Unity en Unity Hub."""
        hub_exe = self.apps.get("unity_hub", {}).get("path")
        if not hub_exe:
            return {"ok": False, "error": "Unity Hub no esta instalado"}

        project = Path(project_path)
        if not project.is_dir():
            return {"ok": False, "error": f"Proyecto no encontrado: {project_path}"}

        try:
            subprocess.Popen([hub_exe, "--open-project", str(project)],
                           creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": f"Unity Hub abriendo: {project_path}"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_jan_status(self) -> Dict[str, Any]:
        """Estado de Jan (modelo local)."""
        jan = self.apps.get("jan", {})
        if not jan.get("installed"):
            return {"installed": False, "running": False, "error": "Jan no instalado"}

        running = self.is_running("jan")
        jan["running"] = running

        if running:
            try:
                import requests
                url = "http://localhost:1337/v1/models"
                resp = requests.get(url, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    return {
                        "installed": True,
                        "running": True,
                        "path": jan["path"],
                        "models": models,
                        "api_url": "http://localhost:1337/v1",
                    }
            except Exception:
                pass

        return {"installed": True, "running": running, "path": jan["path"]}

    def get_all_apps_status(self) -> Dict[str, Any]:
        """Estado de todas las apps."""
        status: Dict[str, Dict[str, Any]] = {}
        for app_name in self.apps:
            running = self.is_running(app_name)
            self.apps[app_name]["running"] = running
            status[app_name] = {
                "installed": self.apps[app_name]["installed"],
                "running": running,
                "path": self.apps[app_name]["path"],
            }

        jan_detail = self.get_jan_status()
        status["jan"] = jan_detail

        return status

    def vs_code_open(self, path: str = "", args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Abre VS Code (con ruta o carpeta opcional)."""
        code = self.apps.get("vs_code", {})
        if not code.get("installed"):
            return {"ok": False, "error": "VS Code no esta instalado"}
        try:
            cmd = [code["path"]]
            if path:
                cmd.append(str(path))
            if args:
                cmd.extend(args)
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": "VS Code abierto", "path": path or None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def antigravity_open(self, path: str = "") -> Dict[str, Any]:
        """Abre Antigravity IDE (con proyecto opcional)."""
        ag = self.apps.get("antigravity", {})
        if not ag.get("installed"):
            return {"ok": False, "error": "Antigravity no esta instalado"}
        try:
            cmd = [ag["path"]]
            if path:
                cmd.append(str(path))
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS)
            return {"ok": True, "message": "Antigravity abierto", "path": path or None}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
