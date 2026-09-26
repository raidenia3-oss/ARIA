"""
AURA WebSocket Server - Control de VS Code desde dashboard
==========================================================
Permite recibir comandos 'file_system' y 'terminal_exec' de forma segura
usando el CLI de VS Code (code -- folder/file).
"""

import json
import asyncio
import os
import subprocess
import sys
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Directorio base del proyecto (para restringir operaciones de archivos)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Whitelist de comandos terminal permitidos (regex/prefix match)
ALLOWED_COMMAND_PREFIXES = [
    "git status",
    "git diff",
    "git log",
    "git branch",
    "git pull",
    "git push",
    "python ",
    "pip install",
    "pip list",
    "npm install",
    "npm run",
    "npm start",
    "npx ",
    "node ",
    "dir ",
    "ls ",
    "echo ",
    "cat ",
    "type ",
    "cd ",
    "pm2 ",
    "mkdir ",
    "copy ",
    "move ",
    "del ",
    "rm ",
]

# Extensiones de archivo permitidas para crear/modificar
ALLOWED_EXTENSIONS = [
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".css",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".sh",
    ".bat",
    ".ps1",
    ".env",
    ".conf",
    ".cfg",
    ".ini",
    ".toml",
    ".gradle",
    ".java",
    ".kt",
    ".xml",
    ".dockerfile",
    ".gitignore",
]


def is_path_safe(relative_path: str) -> bool:
    """Valida que la ruta relativa no escape del directorio del proyecto"""
    if not relative_path or ".." in relative_path:
        return False
    # Normalizar y verificar que no salga del project root
    abs_path = os.path.normpath(os.path.join(PROJECT_ROOT, relative_path))
    return abs_path.startswith(PROJECT_ROOT)


def is_extension_allowed(filename: str) -> bool:
    """Verifica que la extensión del archivo esté en la whitelist"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def is_command_allowed(command: str) -> bool:
    """Verifica que el comando terminal esté en la whitelist"""
    command_stripped = command.strip().lower()
    for prefix in ALLOWED_COMMAND_PREFIXES:
        if command_stripped.startswith(prefix.lower()):
            return True
    return False


async def execute_vscode_command(file_path: str) -> Dict[str, Any]:
    """Abre o crea un archivo en VS Code usando code CLI"""
    try:
        abs_path = os.path.join(PROJECT_ROOT, file_path)
        result = subprocess.run(
            ["code", "--reuse-window", abs_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "success": True,
            "file": file_path,
            "opened_in": "vscode",
            "stderr": result.stderr.strip() if result.stderr else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout al ejecutar code CLI"}
    except FileNotFoundError:
        return {"success": False, "error": "code CLI no encontrado en PATH"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def write_file_safe(relative_path: str, content: str) -> Dict[str, Any]:
    """Escribe contenido en un archivo del proyecto de forma segura"""
    if not is_path_safe(relative_path):
        return {"success": False, "error": "Ruta no permitida (path traversal detectado)"}

    if not is_extension_allowed(relative_path):
        return {
            "success": False,
            "error": f"Extension no permitida: {os.path.splitext(relative_path)[1]}",
        }

    try:
        abs_path = os.path.normpath(os.path.join(PROJECT_ROOT, relative_path))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Abrir en VS Code después de escribir
        await execute_vscode_command(relative_path)

        return {
            "success": True,
            "file": relative_path,
            "size": len(content),
            "action": "created/updated",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def read_file_safe(relative_path: str) -> Dict[str, Any]:
    """Lee contenido de un archivo del proyecto de forma segura"""
    if not is_path_safe(relative_path):
        return {"success": False, "error": "Ruta no permitida"}

    try:
        abs_path = os.path.normpath(os.path.join(PROJECT_ROOT, relative_path))
        if not os.path.exists(abs_path):
            return {"success": False, "error": "Archivo no encontrado"}
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "file": relative_path, "content": content, "size": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def exec_terminal_safe(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Ejecuta un comando en terminal de forma segura con whitelist"""
    if not is_command_allowed(command):
        return {
            "success": False,
            "error": f"Comando no permitido en whitelist: {command.split()[0]}",
        }

    try:
        work_dir = os.path.join(PROJECT_ROOT, cwd) if cwd else PROJECT_ROOT
        if not is_path_safe(cwd or ""):
            return {"success": False, "error": "Directorio de trabajo no permitido"}

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=work_dir,
        )
        return {
            "success": result.returncode == 0,
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "cwd": work_dir,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout - comando excedio 60s", "command": command}
    except Exception as e:
        return {"success": False, "error": str(e), "command": command}


# ===========================================================
# WebSocket Handlers
# ===========================================================


async def handle_file_system(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maneja comandos de sistema de archivos via VS Code.
    Acciones: read, write, open_in_vscode, list_dir
    """
    action = data.get("action", "")
    path = data.get("path", "")
    content = data.get("content", "")

    if not action:
        return {"type": "file_result", "success": False, "error": "Accion no especificada"}
    if not path:
        return {"type": "file_result", "success": False, "error": "Ruta no especificada"}

    try:
        if action == "read":
            result = await read_file_safe(path)
            return {"type": "file_result", **result}

        elif action == "write":
            if not content:
                return {"type": "file_result", "success": False, "error": "Contenido vacio"}
            result = await write_file_safe(path, content)
            return {"type": "file_result", **result}

        elif action == "open_in_vscode":
            if not is_path_safe(path):
                return {"type": "file_result", "success": False, "error": "Ruta no permitida"}
            result = await execute_vscode_command(path)
            return {"type": "file_result", **result}

        elif action == "list_dir":
            if not is_path_safe(path):
                return {"type": "file_result", "success": False, "error": "Ruta no permitida"}
            abs_path = os.path.normpath(os.path.join(PROJECT_ROOT, path))
            if not os.path.isdir(abs_path):
                return {
                    "type": "file_result",
                    "success": False,
                    "error": "Directorio no encontrado",
                }
            items = []
            for entry in os.listdir(abs_path):
                full = os.path.join(abs_path, entry)
                items.append(
                    {
                        "name": entry,
                        "type": "dir" if os.path.isdir(full) else "file",
                        "size": os.path.getsize(full) if os.path.isfile(full) else 0,
                    }
                )
            return {
                "type": "file_result",
                "success": True,
                "path": path,
                "items": items,
                "count": len(items),
            }

        else:
            return {
                "type": "file_result",
                "success": False,
                "error": f"Accion desconocida: {action}",
            }

    except Exception as e:
        return {"type": "file_result", "success": False, "error": str(e)}


async def handle_terminal_exec(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maneja ejecucion segura de comandos en terminal.
    Usa whitelist de comandos para prevenir comandos peligrosos.
    """
    command = data.get("command", "")
    cwd = data.get("cwd", "")

    if not command:
        return {"type": "terminal_result", "success": False, "error": "Comando vacio"}

    result = await exec_terminal_safe(command, cwd if cwd else None)
    return {
        "type": "terminal_result",
        "success": result.get("success", False),
        "command": command,
        "exit_code": result.get("exit_code"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "cwd": PROJECT_ROOT,
    }


# ===========================================================
# Integracion con AURAWebSocketServer original
# ===========================================================

# Manejadores adicionales para inyectar en el servidor WebSocket
VSCODE_HANDLERS: Dict[str, Callable] = {
    "file_system": handle_file_system,
    "terminal_exec": handle_terminal_exec,
}
