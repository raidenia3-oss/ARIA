"""Action Engine for AURA - Extensible Tool Registry with Function Calling.

Provides:
- JSON Schema-compatible tool registry
- Native OS tools: command execution, app launcher, file/dir management, web fetch
- Permission system with explicit confirmation for high-impact actions
- Integration with Swarm orchestrator for environment feedback
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ActionRiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    risk_level: ActionRiskLevel = ActionRiskLevel.SAFE
    requires_confirmation: bool = False
    category: str = "general"
    confirmation_prompt: Optional[str] = None

    def to_json_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": self.parameters.get("properties", {}),
                "required": self.parameters.get("required", []),
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "category": self.category,
            "parameters": self.parameters,
        }


@dataclass
class ActionResult:
    success: bool
    tool_name: str
    output: Any
    error: Optional[str] = None
    risk_level: ActionRiskLevel = ActionRiskLevel.SAFE
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "output": self.output,
            "error": self.error,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_prompt": self.confirmation_prompt,
            "metadata": self.metadata,
        }


class PermissionManager:
    def __init__(self) -> None:
        self._allowed_safe = True
        self._pending_confirmations: Dict[str, Dict[str, Any]] = {}

    def check_permission(self, tool: ToolDefinition, params: Dict[str, Any]) -> ActionResult:
        if tool.risk_level == ActionRiskLevel.SAFE:
            return ActionResult(success=True, tool_name=tool.name, output=None)
        if tool.risk_level in (ActionRiskLevel.LOW, ActionRiskLevel.MEDIUM) and not tool.requires_confirmation:
            return ActionResult(success=True, tool_name=tool.name, output=None)
        prompt = tool.confirmation_prompt or f"Confirmar ejecución de '{tool.name}' con riesgo {tool.risk_level.value}."
        return ActionResult(
            success=False,
            tool_name=tool.name,
            output=None,
            risk_level=tool.risk_level,
            requires_confirmation=True,
            confirmation_prompt=prompt,
        )

    def register_confirmation(self, action_id: str, approved: bool, context: Dict[str, Any]) -> None:
        self._pending_confirmations[action_id] = {"approved": approved, "context": context}


class ActionEngine:
    def __init__(self, orchestrator: Any = None) -> None:
        self.orchestrator = orchestrator
        self._tools: Dict[str, ToolDefinition] = {}
        self._permission_manager = PermissionManager()
        self._action_history: List[Dict[str, Any]] = []
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register_tool(ToolDefinition(
            name="run_command",
            description="Ejecuta un comando del sistema operativo de forma controlada.",
            parameters={
                "properties": {
                    "command": {"type": "string", "description": "Comando a ejecutar."},
                    "timeout": {"type": "integer", "description": "Tiempo límite en segundos.", "default": 30},
                },
                "required": ["command"],
            },
            risk_level=ActionRiskLevel.HIGH,
            requires_confirmation=True,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="launch_app",
            description="Lanza una aplicación de escritorio por nombre o ruta.",
            parameters={
                "properties": {
                    "app": {"type": "string", "description": "Nombre o ruta del ejecutable."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Argumentos opcionales."},
                },
                "required": ["app"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="list_directory",
            description="Lista el contenido de un directorio.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del directorio.", "default": "."},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.SAFE,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="read_file",
            description="Lee el contenido de un archivo de texto.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "limit": {"type": "integer", "description": "Límite de caracteres.", "default": 4000},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="write_file",
            description="Escribe contenido en un archivo de texto.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "content": {"type": "string", "description": "Contenido a escribir."},
                    "mode": {"type": "string", "description": "Modo de escritura.", "default": "w"},
                },
                "required": ["path", "content"],
            },
            risk_level=ActionRiskLevel.HIGH,
            requires_confirmation=True,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="delete_path",
            description="Elimina un archivo o directorio.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta a eliminar."},
                    "recursive": {"type": "boolean", "description": "Eliminar recursivamente si es directorio.", "default": False},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.CRITICAL,
            requires_confirmation=True,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="web_fetch",
            description="Obtiene contenido de una URL pública.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a solicitar."},
                    "method": {"type": "string", "description": "Método HTTP.", "default": "GET"},
                    "headers": {"type": "object", "description": "Encabezados adicionales."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="web",
        ))
        self.register_tool(ToolDefinition(
            name="open_url",
            description="Abre una URL en el navegador predeterminado del sistema.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a abrir."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="web",
        ))
        self.register_tool(ToolDefinition(
            name="browser.open",
            description="Abre una URL en el navegador del sistema (alias de open_url).",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a abrir."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.search",
            description="Busca en Internet y devuelve resultados web.",
            parameters={
                "properties": {
                    "query": {"type": "string", "description": "Consulta de búsqueda."},
                },
                "required": ["query"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.read",
            description="Lee el contenido textual de una página web.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a leer."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.screenshot",
            description="Captura la pantalla actual (requiere pyautogui).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.wait",
            description="Espera N segundos durante una automatización.",
            parameters={
                "properties": {
                    "seconds": {"type": "number", "description": "Segundos a esperar.", "default": 1},
                },
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="files.list",
            description="Alias de list_directory.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del directorio.", "default": "."},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="memory",
        ))

        browser_tools = [
            ("browser.extension_status", "Estado de la extensión AURA en Chrome.", [], ActionRiskLevel.SAFE),
            ("browser.active_tab", "Obtiene información de la pestaña activa.", [], ActionRiskLevel.LOW),
            ("browser.read_visible", "Lee el texto visible de la pestaña activa.", [], ActionRiskLevel.LOW),
            ("browser.open_url", "Abre una URL en Chrome.", ["url"], ActionRiskLevel.MEDIUM),
            ("browser.click", "Haz clic en un selector en la pestaña activa.", ["selector"], ActionRiskLevel.MEDIUM),
            ("browser.type", "Escribe texto en un campo de la pestaña activa.", ["selector", "value"], ActionRiskLevel.MEDIUM),
            ("browser.select", "Selecciona una opción en un <select>.", ["selector", "value"], ActionRiskLevel.MEDIUM),
            ("browser.screenshot", "Toma captura de pantalla de la pestaña activa.", [], ActionRiskLevel.LOW),
            ("browser.stop", "Detiene la tarea activa.", [], ActionRiskLevel.MEDIUM),
        ]
        for name, desc, required, risk in browser_tools:
            props = {}
            if "url" in required:
                props["url"] = {"type": "string", "description": "URL a abrir."}
            if "selector" in required:
                props["selector"] = {"type": "string", "description": "Selector CSS."}
            if "value" in required:
                props["value"] = {"type": "string", "description": "Valor a escribir o seleccionar."}
            self.register_tool(ToolDefinition(
                name=name,
                description=desc,
                parameters={"properties": props, "required": required},
                risk_level=risk,
                requires_confirmation=(risk == ActionRiskLevel.MEDIUM),
                category="browser",
                confirmation_prompt="Esta acción interactúa con tu navegador Chrome. Confirma antes de ejecutar." if risk == ActionRiskLevel.MEDIUM else None,
            ))

        self.register_tool(ToolDefinition(
            name="files.read",
            description="Alias de read_file.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "limit": {"type": "integer", "description": "Límite de caracteres.", "default": 4000},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="files.write",
            description="Alias de write_file.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "content": {"type": "string", "description": "Contenido a escribir."},
                    "mode": {"type": "string", "description": "Modo de escritura.", "default": "w"},
                },
                "required": ["path", "content"],
            },
            risk_level=ActionRiskLevel.HIGH,
            requires_confirmation=True,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="files.move",
            description="Mueve un archivo o directorio a otra ruta.",
            parameters={
                "properties": {
                    "src": {"type": "string", "description": "Ruta origen."},
                    "dst": {"type": "string", "description": "Ruta destino."},
                },
                "required": ["src", "dst"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="files.organize",
            description="Organiza archivos por extensión en subcarpetas.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Directorio a organizar.", "default": "."},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="system.status",
            description="Devuelve estado básico de la PC (CPU, RAM, disco).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="system.apps",
            description="Lista procesos activos del sistema.",
            parameters={
                "properties": {
                    "limit": {"type": "integer", "description": "Límite de resultados.", "default": 20},
                },
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="system.open",
            description="Alias de launch_app.",
            parameters={
                "properties": {
                    "app": {"type": "string", "description": "Nombre o ruta del ejecutable."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Argumentos opcionales."},
                },
                "required": ["app"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="system.screenshot",
            description="Captura la pantalla actual (requiere pyautogui).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        ))
        self.register_tool(ToolDefinition(
            name="automation.create",
            description="Crea una automatización aprendida a partir de pasos.",
            parameters={
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la automatización."},
                    "goal": {"type": "string", "description": "Objetivo de la automatización."},
                    "steps": {"type": "array", "description": "Lista de pasos."},
                },
                "required": ["name", "goal", "steps"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        ))
        self.register_tool(ToolDefinition(
            name="automation.run",
            description="Ejecuta una automatización aprendida por ID.",
            parameters={
                "properties": {
                    "procedure_id": {"type": "string", "description": "ID de la automatización."},
                },
                "required": ["procedure_id"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        ))
        self.register_tool(ToolDefinition(
            name="automation.cancel",
            description="Cancela una automatización en ejecución por ID de tarea.",
            parameters={
                "properties": {
                    "task_id": {"type": "string", "description": "ID de la tarea."},
                },
                "required": ["task_id"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        ))
        self.register_tool(ToolDefinition(
            name="automation.save",
            description="Guarda una tarea completada como procedimiento reutilizable.",
            parameters={
                "properties": {
                    "task_id": {"type": "string", "description": "ID de la tarea completada."},
                    "name": {"type": "string", "description": "Nombre del procedimiento."},
                    "goal": {"type": "string", "description": "Objetivo del procedimiento."},
                },
                "required": ["task_id", "name"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        ))
        self.register_tool(ToolDefinition(
            name="automation.run_procedure",
            description="Ejecuta un procedimiento guardado por ID.",
            parameters={
                "properties": {
                    "procedure_id": {"type": "string", "description": "ID del procedimiento aprendido."},
                    "params": {"type": "object", "description": "Parámetros para sobreescibir los steps del procedimiento."},
                },
                "required": ["procedure_id"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        ))
        self.register_tool(ToolDefinition(
            name="memory.remember",
            description="Guarda un recuerdo en la memoria de AURA.",
            parameters={
                "properties": {
                    "text": {"type": "string", "description": "Texto a recordar."},
                    "type": {"type": "string", "description": "Tipo de memoria.", "default": "episodic"},
                    "source": {"type": "string", "description": "Fuente.", "default": "user"},
                },
                "required": ["text"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="memory",
        ))
        self.register_tool(ToolDefinition(
            name="memory.search",
            description="Busca en la memoria de AURA.",
            parameters={
                "properties": {
                    "query": {"type": "string", "description": "Consulta de búsqueda."},
                    "limit": {"type": "integer", "description": "Límite de resultados.", "default": 5},
                },
                "required": ["query"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="memory",
        ))


    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def execute(self, tool_name: str, params: Dict[str, Any]) -> ActionResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ActionResult(success=False, tool_name=tool_name, output=None, error="tool_not_found")
        perm = self._permission_manager.check_permission(tool, params)
        if not perm.success and perm.requires_confirmation:
            return perm
        try:
            output = self._run_tool(tool, params)
            result = ActionResult(success=True, tool_name=tool_name, output=output, risk_level=tool.risk_level, requires_confirmation=tool.requires_confirmation)
            self._action_history.append(result.to_dict())
            self._inject_into_orchestrator(result)
            return result
        except Exception as exc:
            result = ActionResult(success=False, tool_name=tool_name, output=None, error=str(exc), risk_level=tool.risk_level)
            self._action_history.append(result.to_dict())
            return result

    def _run_tool(self, tool: ToolDefinition, params: Dict[str, Any]) -> Any:
        name = tool.name
        if name == "run_command":
            return self._tool_run_command(params)
        if name == "launch_app" or name == "system.open":
            return self._tool_launch_app(params)
        if name == "list_directory" or name == "files.list":
            return self._tool_list_directory(params)
        if name == "read_file" or name == "files.read":
            return self._tool_read_file(params)
        if name == "write_file" or name == "files.write":
            return self._tool_write_file(params)
        if name == "delete_path":
            return self._tool_delete_path(params)
        if name == "web_fetch" or name == "browser.read":
            return self._tool_web_fetch(params)
        if name == "open_url" or name == "browser.open":
            return self._tool_open_url(params)
        if name == "browser.search":
            return self._tool_browser_search(params)
        if name == "browser.screenshot" or name == "system.screenshot":
            return self._tool_screenshot(params)
        if name == "browser.wait":
            return self._tool_wait(params)
        if name == "files.move":
            return self._tool_files_move(params)
        if name == "files.organize":
            return self._tool_files_organize(params)
        if name == "system.status":
            return self._tool_system_status()
        if name == "system.apps":
            return self._tool_system_apps(params)
        if name == "automation.create":
            return self._tool_automation_create(params)
        if name == "automation.run":
            return self._tool_automation_run(params)
        if name == "automation.cancel":
            return self._tool_automation_cancel(params)
        if name == "automation.save":
            return self._tool_automation_save(params)
        if name == "automation.run_procedure":
            return self._tool_automation_run_procedure(params)
        if name == "memory.remember":
            return self._tool_memory_remember(params)
        if name == "memory.search":
            return self._tool_memory_search(params)
        if name.startswith("browser."):
            return self._tool_browser(name, params)
        raise ValueError(f"Herramienta no implementada: {name}")

    def _tool_run_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = str(params.get("command", "")).strip()
        timeout = int(params.get("timeout", 30))
        if not command:
            return {"stdout": "", "stderr": "", "returncode": -1}
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "timeout", "returncode": -1}

    def _tool_launch_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        app = str(params.get("app", "")).strip()
        args = params.get("args", [])
        if not app:
            return {"launched": False, "error": "app_required"}
        cmd = [app]
        cmd.extend(str(a) for a in args)
        try:
            subprocess.Popen(cmd, shell=False)
            return {"launched": True, "command": cmd}
        except Exception as exc:
            try:
                subprocess.Popen(cmd, shell=True)
                return {"launched": True, "command": cmd}
            except Exception as exc2:
                return {"launched": False, "error": str(exc2)}

    def _tool_list_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = str(params.get("path", ".")).strip()
        try:
            entries = []
            for name in os.listdir(path):
                full = os.path.join(path, name)
                entries.append({"name": name, "is_dir": os.path.isdir(full), "size": os.path.getsize(full) if os.path.isfile(full) else None})
            return {"path": path, "entries": entries}
        except Exception as exc:
            return {"path": path, "entries": [], "error": str(exc)}

    def _tool_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = str(params.get("path", "")).strip()
        limit = int(params.get("limit", 4000))
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(limit)
            return {"path": path, "content": content}
        except Exception as exc:
            return {"path": path, "content": "", "error": str(exc)}

    def _tool_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = str(params.get("path", "")).strip()
        content = str(params.get("content", ""))
        mode = str(params.get("mode", "w"))
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            return {"path": path, "written": True, "mode": mode}
        except Exception as exc:
            return {"path": path, "written": False, "error": str(exc)}

    def _tool_delete_path(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = str(params.get("path", "")).strip()
        recursive = bool(params.get("recursive", False))
        try:
            if not os.path.exists(path):
                return {"path": path, "deleted": False, "error": "not_found"}
            if os.path.isdir(path) and recursive:
                shutil.rmtree(path)
            elif os.path.isdir(path) and not recursive:
                os.rmdir(path)
            else:
                os.remove(path)
            return {"path": path, "deleted": True}
        except Exception as exc:
            return {"path": path, "deleted": False, "error": str(exc)}

    def _tool_web_fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = str(params.get("url", "")).strip()
        method = str(params.get("method", "GET")).upper()
        headers = params.get("headers", {})
        if not url:
            return {"status_code": 0, "body": "", "error": "url_required"}
        try:
            req = urllib.request.Request(url, method=method, headers={str(k): str(v) for k, v in headers.items()})
            with urllib.request.urlopen(req, timeout=15) as response:
                body = response.read(4096).decode("utf-8", errors="ignore")
                return {"status_code": response.status, "body": body}
        except urllib.error.HTTPError as exc:
            return {"status_code": exc.code, "body": "", "error": str(exc)}
        except Exception as exc:
            return {"status_code": 0, "body": "", "error": str(exc)}

    def _tool_open_url(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = str(params.get("url", "")).strip()
        if not url:
            return {"opened": False, "error": "url_required"}
        try:
            system = platform.system().lower()
            if system == "windows":
                os.startfile(url)
            elif system == "darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
            return {"opened": True, "url": url}
        except Exception as exc:
            return {"opened": False, "error": str(exc)}

    def _inject_into_orchestrator(self, result: ActionResult) -> None:
        if not self.orchestrator:
            return
        try:
            if hasattr(self.orchestrator, "set_action_result"):
                self.orchestrator.set_action_result(result.to_dict())
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "tool_count": len(self._tools),
            "history_count": len(self._action_history),
            "last_actions": self._action_history[-5:],
            "tools": [tool.to_dict() for tool in self._tools.values()],
        }

    def _tool_browser_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = str(params.get("query", "")).strip()
        if not query:
            return {"results": [], "error": "query_required"}
        url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        return self._tool_web_fetch({"url": url})

    def _tool_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import pyautogui
            img = pyautogui.screenshot()
            return {"captured": True, "width": img.width, "height": img.height, "mode": img.mode}
        except Exception as exc:
            return {"captured": False, "error": str(exc)}

    def _tool_wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import time as _time
        seconds = float(params.get("seconds", 1))
        _time.sleep(seconds)
        return {"waited": True, "seconds": seconds}

    def _tool_files_move(self, params: Dict[str, Any]) -> Dict[str, Any]:
        src = str(params.get("src", "")).strip()
        dst = str(params.get("dst", "")).strip()
        try:
            import shutil
            shutil.move(src, dst)
            return {"moved": True, "src": src, "dst": dst}
        except Exception as exc:
            return {"moved": False, "error": str(exc)}

    def _tool_files_organize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        base = str(params.get("path", ".")).strip()
        moved = 0
        try:
            for name in os.listdir(base):
                full = os.path.join(base, name)
                if os.path.isfile(full):
                    ext = os.path.splitext(name)[1].lower().strip(".") or "unknown"
                    target_dir = os.path.join(base, ext)
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.move(full, os.path.join(target_dir, name))
                    moved += 1
            return {"organized": True, "moved": moved, "path": base}
        except Exception as exc:
            return {"organized": False, "moved": moved, "error": str(exc)}

    def _tool_system_status(self) -> Dict[str, Any]:
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory": psutil.virtual_memory()._asdict(),
                "disk": psutil.disk_usage(os.path.expanduser("~"))._asdict(),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _tool_system_apps(self, params: Dict[str, Any]) -> Dict[str, Any]:
        limit = int(params.get("limit", 20))
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                procs.append(p.info)
            return {"apps": procs[:limit]}
        except Exception as exc:
            return {"apps": [], "error": str(exc)}

    def _tool_automation_create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            name = str(params.get("name", "")).strip()
            goal = str(params.get("goal", "")).strip()
            steps = params.get("steps", [])
            if not name or not steps:
                return {"created": False, "error": "name and steps are required"}
            result = asyncio.get_event_loop().run_until_complete(
                task_manager.learn_procedure(name, steps, goal)
            )
            return {"created": True, "procedure": result}
        except Exception as exc:
            return {"created": False, "error": str(exc)}

    def _tool_automation_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            proc_id = str(params.get("procedure_id", "")).strip()
            proc = asyncio.get_event_loop().run_until_complete(task_manager.get_learned_procedure(proc_id))
            if not proc:
                return {"started": False, "error": "procedure_not_found"}
            steps = proc.get("steps", [])
            task = asyncio.get_event_loop().run_until_complete(
                task_manager.create_task(name=proc["name"], action_type="automation", goal=proc["goal"], parameters={"procedure_id": proc_id})
            )
            asyncio.get_event_loop().run_until_complete(task_manager.start_task(task.task_id, steps))
            asyncio.get_event_loop().run_until_complete(task_manager.increment_procedure_execution(proc_id))
            return {"started": True, "task_id": task.task_id}
        except Exception as exc:
            return {"started": False, "error": str(exc)}

    def _tool_automation_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager
            task_id = str(params.get("task_id", "")).strip()
            result = asyncio.get_event_loop().run_until_complete(task_manager.cancel_task(task_id))
            return {"cancelled": result}
        except Exception as exc:
            return {"cancelled": False, "error": str(exc)}

    def _tool_memory_remember(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.routers.memory import memory_engine
            text = str(params.get("text", "")).strip()
            memory_type = str(params.get("type", "episodic"))
            source = str(params.get("source", "user"))
            if not text:
                return {"remembered": False, "error": "text is required"}
            result = memory_engine.remember(text, memory_type=memory_type, source=source)
            return {"remembered": True, "memory": result}
        except Exception as exc:
            return {"remembered": False, "error": str(exc)}

    def _tool_memory_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.routers.memory import memory_engine
            query = str(params.get("query", "")).strip()
            limit = int(params.get("limit", 5))
            if not query:
                return {"results": [], "error": "query is required"}
            result = memory_engine.search(query, max_results=limit)
            return {"results": result.get("results", [])}
        except Exception as exc:
            return {"results": [], "error": str(exc)}

    def _tool_automation_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager

            task_id = str(params.get("task_id", "")).strip()
            name = str(params.get("name", "")).strip()
            goal = str(params.get("goal", "")).strip()
            if not task_id or not name:
                return {"saved": False, "error": "task_id and name are required"}
            result = asyncio.get_event_loop().run_until_complete(
                task_manager.capture_task_to_procedure(task_id, name, goal)
            )
            return {"saved": True, "procedure": result}
        except Exception as exc:
            return {"saved": False, "error": str(exc)}

    def _tool_automation_run_procedure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import asyncio
            from backend.task_manager import task_manager

            proc_id = str(params.get("procedure_id", "")).strip()
            run_params = params.get("params", {})
            if not proc_id:
                return {"started": False, "error": "procedure_id is required"}
            result = asyncio.get_event_loop().run_until_complete(
                task_manager.run_procedure(proc_id, params_override=run_params or {})
            )
            return {"started": True, "task_id": result["task_id"]}
        except Exception as exc:
            return {"started": False, "error": str(exc)}

    def _tool_browser(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        from backend.browser_task_manager import browser_task_manager
        import secrets as _secrets

        ext_status = browser_task_manager.list()
        active_task = next((t for t in ext_status if t["status"] == "pending"), None)

        if name == "browser.extension_status":
            return {"status": "ok", "data": {"connected": len(ext_status) > 0, "active_tasks": len(ext_status)}}

        if name == "browser.stop":
            if active_task:
                browser_task_manager.cancel(active_task["task_id"])
                return {"status": "ok", "data": {"stopped": True, "task_id": active_task["task_id"]}}
            return {"status": "ok", "data": {"stopped": False, "reason": "no_active_task"}}

        if active_task:
            return {"status": "error", "error": "browser_busy", "data": {"active_task": active_task["task_id"]}}

        task_id = f"browsertask-{_secrets.token_hex(6)}"
        import uuid as _uuid

        if name == "browser.open_url":
            url = str(params.get("url", "")).strip()
            if not url:
                return {"status": "error", "error": "url required"}
            browser_task_manager.create(task_id, "open_url", url)
            _send_browser_command("open_url", {"url": url}, task_id)
            return {"status": "ok", "data": {"task_id": task_id, "url": url}}

        if name == "browser.read_visible":
            browser_task_manager.create(task_id, "read_visible", "")
            _send_browser_command("read_visible", {}, task_id)
            return {"status": "ok", "data": {"task_id": task_id}}

        if name == "browser.click":
            selector = str(params.get("selector", "")).strip()
            if not selector:
                return {"status": "error", "error": "selector required"}
            browser_task_manager.create(task_id, "click", "")
            _send_browser_command("click", {"selector": selector}, task_id)
            return {"status": "ok", "data": {"task_id": task_id, "selector": selector}}

        if name == "browser.type":
            selector = str(params.get("selector", "")).strip()
            value = str(params.get("value", "")).strip()
            if not selector:
                return {"status": "error", "error": "selector required"}
            browser_task_manager.create(task_id, "type", "")
            _send_browser_command("type", {"selector": selector, "value": value}, task_id)
            return {"status": "ok", "data": {"task_id": task_id, "selector": selector}}

        if name == "browser.select":
            selector = str(params.get("selector", "")).strip()
            value = str(params.get("value", "")).strip()
            if not selector:
                return {"status": "error", "error": "selector required"}
            browser_task_manager.create(task_id, "select", "")
            _send_browser_command("select", {"selector": selector, "value": value}, task_id)
            return {"status": "ok", "data": {"task_id": task_id, "selector": selector}}

        if name == "browser.screenshot":
            browser_task_manager.create(task_id, "screenshot", "")
            _send_browser_command("screenshot", {}, task_id)
            return {"status": "ok", "data": {"task_id": task_id}}

        if name == "browser.active_tab":
            _send_browser_command("active_tab", {}, task_id)
            browser_task_manager.create(task_id, "active_tab", "")
            return {"status": "ok", "data": {"task_id": task_id}}

        return {"status": "error", "error": "unknown_browser_action"}


def _send_browser_command(action: str, data: Dict[str, Any], task_id: str) -> None:
    """Envía un comando al browser_task_manager para registro (actualmente no hay WebSocket directo desde backend)."""
    pass
