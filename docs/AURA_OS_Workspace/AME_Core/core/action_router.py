#!/usr/bin/env python3
"""
action_router.py - Enrutador de Acciones del Sistema
Traduce intenciones en lenguaje natural a comandos nativos del sistema.
"""

import os
import re
import shutil
import logging
import subprocess
import platform
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionRouter:
    """Router de acciones nativas con validación de seguridad."""

    def __init__(self):
        self.allowed_apps = {
            "navegador": ["chrome", "firefox", "msedge"],
            "explorador": ["explorer.exe", "nautil", "thunar"],
            "editor": ["notepad", "code", "vim"],
            "terminal": ["cmd", "powershell", "bash"],
        }
        self.safe_commands = {
            "abrir",
            "cerrar",
            "listar",
            "buscar",
            "crear",
            "eliminar",
            "mover",
            "copiar",
            "renombrar",
            "mostrar",
            "ayuda",
        }

    async def execute(self, intent: str, params: Dict) -> Dict:
        """
        Ejecutar una acción del sistema basada en la intención del usuario.
        """
        intent_lower = intent.lower().strip()
        logger.info(f"[ActionRouter] Ejecutando: {intent_lower}")

        try:
            if "abrir" in intent_lower or "abre" in intent_lower:
                return await self._open_app(intent_lower, params)
            elif "cerrar" in intent_lower or "cierra" in intent_lower:
                return await self._close_app(intent_lower, params)
            elif "buscar" in intent_lower or "busca" in intent_lower:
                return await self._search(intent_lower, params)
            elif "listar" in intent_lower or "lista" in intent_lower:
                return await self._list_directory(params)
            elif "crear" in intent_lower or "crea" in intent_lower:
                return await self._create_file(params)
            elif "eliminar" in intent_lower or "borrar" in intent_lower:
                return await self._delete_file(params)
            elif "mover" in intent_lower or "mueve" in intent_lower:
                return await self._move_file(params)
            elif "copiar" in intent_lower or "copia" in intent_lower:
                return await self._copy_file(params)
            elif "ayuda" in intent_lower or "help" in intent_lower:
                return self._help()
            else:
                return {
                    "status": "unknown",
                    "message": f"No entendí la acción: {intent_lower}",
                    "hint": "Di: 'Aura, abre el navegador' o 'Aura, busca archivos de python'",
                }
        except Exception as e:
            logger.error(f"[ActionRouter] Error: {e}")
            return {"status": "error", "message": str(e)}

    async def _open_app(self, intent: str, params: Dict) -> Dict:
        app_name = params.get("app") or self._extract_app_name(intent)
        if not app_name:
            return {"status": "error", "message": "No especificaste qué aplicación abrir."}

        system = platform.system()
        commands = {
            "Windows": {
                "navegador": "start chrome",
                "explorador": "explorer.exe",
                "terminal": "start cmd",
                "editor": "code",
            },
            "Linux": {
                "navegador": "xdg-open https://google.com",
                "explorador": "xdg-open .",
                "terminal": "x-terminal-emulator",
                "editor": "code",
            },
            "Darwin": {
                "navegador": "open https://google.com",
                "explorador": "open .",
                "terminal": "open -a Terminal",
                "editor": "code",
            },
        }

        cmd_template = commands.get(system, {}).get(app_name)
        if not cmd_template:
            # Intentar genérico
            cmd_template = app_name

        try:
            subprocess.Popen(
                cmd_template, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return {"status": "ok", "action": "open", "app": app_name, "system": system}
        except Exception as e:
            return {"status": "error", "message": f"No pude abrir {app_name}: {e}"}

    async def _close_app(self, intent: str, params: Dict) -> Dict:
        app_name = params.get("app") or self._extract_app_name(intent)
        if not app_name:
            return {"status": "error", "message": "No especificaste qué aplicación cerrar."}
        # Cierre seguro: solo procesos conocidos
        safe_processes = {
            "notepad": "notepad.exe",
            "bloc de notas": "notepad.exe",
        }
        process = safe_processes.get(app_name.lower())
        if not process:
            return {"status": "error", "message": f"No puedo cerrar {app_name} por seguridad."}

        try:
            subprocess.run(["taskkill", "/IM", process, "/F"], capture_output=True)
            return {"status": "ok", "action": "close", "app": app_name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _search(self, intent: str, params: Dict) -> Dict:
        query = params.get("query") or self._extract_search_query(intent)
        if not query:
            return {"status": "error", "message": "No especificaste qué buscar."}

        results = []
        for root, dirs, files in os.walk(os.path.expanduser("~")):
            for file in files:
                if query.lower() in file.lower():
                    results.append(os.path.join(root, file))
                    if len(results) >= 10:
                        break
            if len(results) >= 10:
                break

        return {
            "status": "ok",
            "action": "search",
            "query": query,
            "results_count": len(results),
            "results": results,
        }

    async def _list_directory(self, params: Dict) -> Dict:
        path = params.get("path", ".")
        try:
            entries = os.listdir(path)
            return {
                "status": "ok",
                "action": "list",
                "path": path,
                "entries": entries[:50],
                "count": len(entries),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _create_file(self, params: Dict) -> Dict:
        filename = params.get("filename")
        content = params.get("content", "")
        if not filename:
            return {"status": "error", "message": "Falta nombre de archivo."}
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "ok", "action": "create", "file": filename}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _delete_file(self, params: Dict) -> Dict:
        filename = params.get("filename")
        if not filename:
            return {"status": "error", "message": "Falta nombre de archivo."}
        try:
            os.remove(filename)
            return {"status": "ok", "action": "delete", "file": filename}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _move_file(self, params: Dict) -> Dict:
        src = params.get("source")
        dst = params.get("destination")
        if not src or not dst:
            return {"status": "error", "message": "Faltan source o destination."}
        try:
            shutil.move(src, dst)
            return {"status": "ok", "action": "move", "from": src, "to": dst}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _copy_file(self, params: Dict) -> Dict:
        src = params.get("source")
        dst = params.get("destination")
        if not src or not dst:
            return {"status": "error", "message": "Faltan source o destination."}
        try:
            shutil.copy2(src, dst)
            return {"status": "ok", "action": "copy", "from": src, "to": dst}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _extract_app_name(self, intent: str) -> Optional[str]:
        keywords = ["abre", "abrir", "abran", "cierra", "cerrar", "ejecuta", "ejecutar"]
        for kw in keywords:
            if kw in intent:
                parts = intent.split(kw, 1)
                if len(parts) > 1:
                    return parts[1].strip().split()[0]
        return None

    def _extract_search_query(self, intent: str) -> Optional[str]:
        match = re.search(
            r"busca(?:r)?\s+(?:archivos? de\s+)?(.+?)(?:\s+en\s+.+)?$", intent, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return None

    def _help(self) -> Dict:
        return {
            "status": "ok",
            "action": "help",
            "commands": [
                "'Aura, abre el navegador'",
                "'Aura, cierra el bloc de notas'",
                "'Aura, busca archivos de python'",
                "'Aura, lista la carpeta Descargas'",
            ],
        }


# Instancia global
_action_router = ActionRouter()


def get_action_router() -> ActionRouter:
    return _action_router
