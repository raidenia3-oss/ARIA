"""ARIA Tool Registry — AI outputs structured tags, Python routes to actions."""

from __future__ import annotations

import re
import subprocess
import json
import os
import time
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: str = ""
    error: str = ""
    execution_time_ms: float = 0.0


@dataclass
class ToolDef:
    name: str
    description: str
    category: str
    handler: Callable
    parameters: List[str] = field(default_factory=list)
    danger_level: str = "safe"  # safe / cautious / dangerous


TOOL_TAG_RE = re.compile(r"\[TOOL:(\w+)\]\s*\{([^}]*)\}", re.IGNORECASE)


class ToolRegistry:
    """Maps AI-generated [TOOL:name]{params} tags to Python handlers."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDef] = {}
        self._history: List[Dict[str, Any]] = []
        self._safety = True  # safety filter enabled

    def register(self, name: str, description: str, category: str,
                 handler: Callable, parameters: List[str] = None,
                 danger_level: str = "safe") -> None:
        self._tools[name] = ToolDef(
            name=name, description=description, category=category,
            handler=handler, parameters=parameters or [], danger_level=danger_level,
        )

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": t.name, "category": t.category, "description": t.description,
             "danger_level": t.danger_level, "parameters": t.parameters}
            for t in self._tools.values()
        ]

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def parse_command(self, text: str) -> List[Dict[str, str]]:
        """Extract [TOOL:name]{params} tags from AI output."""
        matches = []
        for m in TOOL_TAG_RE.finditer(text):
            matches.append({"tool": m.group(1).lower(), "params_raw": m.group(2)})
        return matches

    def has_tools_in_text(self, text: str) -> bool:
        return bool(TOOL_TAG_RE.search(text))

    def strip_tool_tags(self, text: str) -> str:
        return TOOL_TAG_RE.sub("", text).strip()

    def execute(self, tool_name: str, params_raw: str,
                context: Dict[str, Any] = None) -> ToolResult:
        """Execute a single tool call."""
        start = time.time()
        tool = self._tools.get(tool_name.lower())
        if not tool:
            return ToolResult(tool_name=tool_name, success=False,
                              error=f"Herramienta no registrada: {tool_name}")

        params = self._parse_params(params_raw, tool.parameters)

        # Safety check for dangerous tools
        if tool.danger_level == "dangerous" and self._safety:
            return ToolResult(tool_name=tool_name, success=False,
                              error=f"Herramienta peligrosa bloqueada: {tool_name}. "
                                    f"Requiere confirmación explícita del usuario.")

        if tool.danger_level == "cautious" and self._safety:
            context = context or {}
            if not context.get("user_confirmed", False):
                return ToolResult(tool_name=tool_name, success=False,
                                  error=f"Herramienta requiere confirmación: {tool_name}",
                                  output=json.dumps({"requires_confirmation": True,
                                                      "tool": tool_name,
                                                      "params": params}))

        try:
            output = tool.handler(params, context or {})
            elapsed = (time.time() - start) * 1000
            result = ToolResult(tool_name=tool_name, success=True,
                                output=str(output), execution_time_ms=round(elapsed, 2))
            self._history.append({
                "tool": tool_name, "params": params, "success": True,
                "timestamp": time.time(), "duration_ms": elapsed,
            })
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            result = ToolResult(tool_name=tool_name, success=False,
                                error=str(e), execution_time_ms=round(elapsed, 2))
            self._history.append({
                "tool": tool_name, "params": params, "success": False,
                "error": str(e), "timestamp": time.time(), "duration_ms": elapsed,
            })
            return result

    def execute_all(self, text: str, context: Dict[str, Any] = None) -> Tuple[str, List[ToolResult]]:
        """Parse all tool tags in text, execute them, return cleaned text + results."""
        tools = self.parse_command(text)
        if not tools:
            return text, []

        results = []
        for t in tools:
            r = self.execute(t["tool"], t["params_raw"], context)
            results.append(r)

        cleaned = self.strip_tool_tags(text)
        return cleaned, results

    def _parse_params(self, raw: str, expected: List[str]) -> Dict[str, str]:
        params = {}
        if not raw:
            return params
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        for key in expected:
            pattern = re.compile(rf'"?{key}"?\s*[:=]\s*"?([^"\s,]+)"?', re.IGNORECASE)
            m = pattern.search(raw)
            if m:
                params[key] = m.group(1)
        return params

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._history)
        successes = sum(1 for h in self._history if h.get("success"))
        return {
            "registered_tools": len(self._tools),
            "total_executions": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": round(successes / total * 100, 1) if total else 0,
            "tools": [t.name for t in self._tools.values()],
        }


def create_default_registry() -> ToolRegistry:
    """Creates a ToolRegistry with common AURA tools pre-registered."""
    registry = ToolRegistry()

    def _open_app(params: dict, ctx: dict) -> str:
        app = params.get("name", "")
        subprocess.Popen(["start", "", app], shell=True)
        return f"Abriendo: {app}"

    def _search_web(params: dict, ctx: dict) -> str:
        query = params.get("query", "")
        webbrowser_path = os.path.join(os.path.dirname(os.__file__), "webbrowser.py")
        subprocess.Popen([os.sys.executable, "-c", f"import webbrowser; webbrowser.open('{query}')"])
        return f"Buscando: {query}"

    def _capture_screenshot(params: dict, ctx: dict) -> str:
        try:
            import pyautogui
            path = params.get("path", f"screenshot_{int(time.time())}.png")
            pyautogui.screenshot(path)
            return f"Captura guardada: {path}"
        except Exception as e:
            return f"Error capturando: {e}"

    def _read_file(params: dict, ctx: dict) -> str:
        path = params.get("path", "")
        if not path:
            return "Error: se requiere 'path'"
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")[:5000]
        except Exception as e:
            return f"Error leyendo {path}: {e}"

    def _write_file(params: dict, ctx: dict) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        if not path:
            return "Error: se requiere 'path'"
        try:
            Path(path).write_text(content, encoding="utf-8")
            return f"Archivo escrito: {path}"
        except Exception as e:
            return f"Error escribiendo {path}: {e}"

    def _get_system_info(params: dict, ctx: dict) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage(os.path.expanduser("~")).percent
            return json.dumps({"cpu": cpu, "memory": mem, "disk": disk})
        except Exception as e:
            return json.dumps({"error": str(e)})

    registry.register("open_app", "Abrir una aplicación", "system", _open_app,
                       ["name"], "cautious")
    registry.register("search_web", "Buscar en la web", "web", _search_web,
                       ["query"], "safe")
    registry.register("screenshot", "Capturar pantalla", "system", _capture_screenshot,
                       ["path"], "safe")
    registry.register("read_file", "Leer archivo", "files", _read_file,
                       ["path"], "safe")
    registry.register("write_file", "Escribir archivo", "files", _write_file,
                       ["path", "content"], "cautious")
    registry.register("system_info", "Info del sistema", "system", _get_system_info,
                       [], "safe")
    registry.register("control_pc", "Control PC (mouse/teclado)", "system", _control_pc,
                       ["action"], "dangerous")
    registry.register("explorer", "Explorador de archivos", "files", _explorer,
                       ["action", "path"], "safe")
    registry.register("code_run", "Ejecutar código", "system", _code_run,
                       ["code"], "dangerous")
    registry.register("browser", "Navegador web", "web", _browser,
                       ["action", "url"], "safe")

    return registry


def _control_pc(params: dict, ctx: dict) -> str:
    try:
        from backend.skills.system.control import run as ctrl
        result = ctrl(params)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {e}"


def _explorer(params: dict, ctx: dict) -> str:
    try:
        from backend.skills.system.explorer import run as exp
        result = exp(params)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {e}"


def _code_run(params: dict, ctx: dict) -> str:
    try:
        from backend.skills.system.code_exec import run as ce
        result = ce(params)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {e}"


def _browser(params: dict, ctx: dict) -> str:
    try:
        from backend.skills.web.automation import run as auto
        result = auto(params)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {e}"
