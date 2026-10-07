"""AURA Local Specialized Skills & Dynamic Tool-Registry Engine (Bloque 56).

Registro dinamico, carga y ejecucion aislada (sandbox) de herramientas y
habilidades especializadas 100%% locales. No depende de tiendas de extensiones
ni APIs cloud: escanea modulos de Python ubicados en ``backend/agents/tools``
e inyecta sus esquemas de funcion (function-calling) al modelo local
(Jan / Ollama) de forma compatible con OpenAI.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Deque, Dict, List, Optional

logger = logging.getLogger("AURA.Agent.ToolsRegistry")

# Permission engine integration
try:
    from backend.permissions import get_permission_engine
except Exception:  # pragma: no cover
    get_permission_engine = None

# Limite de tasa por herramienta, ventana deslizante. entry.calls es un total
# desde el arranque y no puede expresar "N por ventana": un agente que dispara
# 500 llamadas en un minuto y otro que las reparte en una hora son
# indistinguibles con un contador acumulado. Las marcas de tiempo viven en el
# sandbox. Poner AURA_TOOL_RATE_LIMIT<=0 desactiva el limite.
TOOL_RATE_LIMIT = int(os.environ.get("AURA_TOOL_RATE_LIMIT", "120"))
TOOL_RATE_WINDOW = float(os.environ.get("AURA_TOOL_RATE_WINDOW", "60"))

# Conversores de tipos para argumentos tipados (function-calling).
TYPE_CONVERTERS: Dict[str, Callable[[Any], Any]] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": lambda _v: None,
}


@dataclass
class ToolEntry:
    """Herramienta registrada y ejecutable."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]
    category: str = "general"
    risk: str = "safe"
    module: str = ""
    source: str = "manual"
    registered_at: float = field(default_factory=time.time)
    calls: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "risk": self.risk,
            "parameters": self.parameters,
            "module": self.module,
            "source": self.source,
            "registered_at": self.registered_at,
            "calls": self.calls,
            "last_error": self.last_error,
        }

    def to_function_schema(self) -> Dict[str, Any]:
        """Esquema compatible con function-calling de Jan/Ollama (OpenAI)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class SkillExecutionSandbox:
    """Ejecuta herramientas locales con argumentos tipados de forma segura.

    Solo se invocan referencias a funciones cargadas desde modulos locales
    previamente validados (nunca codigo arbitrario via REST). Captura
    excepciones, timeouts y serializa la salida de forma estructurada.
    """

    def __init__(self, registry: "DynamicToolRegistry") -> None:
        self.registry = registry
        self._windows: Dict[str, Deque[float]] = {}
        self._rejected: Dict[str, int] = {}

    def _rate_limit_reason(self, name: str) -> Optional[str]:
        """Sliding-window guard. Devuelve el motivo si la herramienta excedio el presupuesto.

        Una llamada rechazada no se registra en la ventana: nunca llego a la
        herramienta, asi que cobrarla solo serviria para que un bucle la tenga
        ocupada igual. El conteo de rechazos va aparte para que el limite sea
        observable en vez de fallar en silencio.
        """
        if TOOL_RATE_LIMIT <= 0:
            return None
        now = time.monotonic()
        window = self._windows.setdefault(name, deque())
        while window and now - window[0] >= TOOL_RATE_WINDOW:
            window.popleft()
        if len(window) >= TOOL_RATE_LIMIT:
            self._rejected[name] = self._rejected.get(name, 0) + 1
            return (
                f"rate limit: '{name}' supero {TOOL_RATE_LIMIT} llamadas "
                f"en {TOOL_RATE_WINDOW:g}s"
            )
        window.append(now)
        return None

    def rate_limit_state(self) -> Dict[str, int]:
        """Llamadas rechazadas por limite de tasa, por herramienta."""
        return dict(self._rejected)

    def _coerce_args(self, entry: ToolEntry, params: Dict[str, Any]) -> Dict[str, Any]:
        props = (entry.parameters or {}).get("properties", {})
        required = (entry.parameters or {}).get("required", []) or []
        missing = [k for k in required if k not in params]
        if missing:
            raise ValueError(f"faltan argumentos requeridos: {', '.join(missing)}")
        coerced: Dict[str, Any] = {}
        for key, value in params.items():
            if key not in props:
                coerced[key] = value
                continue
            ptype = (props[key] or {}).get("type", "string")
            converter = TYPE_CONVERTERS.get(ptype)
            if converter is None or value is None:
                coerced[key] = value
                continue
            try:
                coerced[key] = converter(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"argumento '{key}' no valido como {ptype}: {exc}") from exc
        return coerced

    async def _invoke(self, func: Callable[..., Any], kwargs: Dict[str, Any], timeout: float) -> Any:
        if inspect.iscoroutinefunction(func):
            return await asyncio.wait_for(func(**kwargs), timeout=timeout)
        return await asyncio.wait_for(asyncio.to_thread(func, **kwargs), timeout=timeout)

    async def execute(
        self,
        entry: ToolEntry,
        params: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        limit_error = self._rate_limit_reason(entry.name)
        if limit_error is not None:
            entry.last_error = limit_error
            return {
                "success": False, "tool": entry.name, "output": None,
                "error": limit_error, "duration_ms": (time.perf_counter() - start) * 1000.0,
            }
        try:
            kwargs = self._coerce_args(entry, dict(params or {}))
        except ValueError as exc:
            entry.last_error = str(exc)
            entry.calls += 1
            return {
                "success": False, "tool": entry.name, "output": None,
                "error": str(exc), "duration_ms": (time.perf_counter() - start) * 1000.0,
            }
        try:
            output = await self._invoke(entry.func, kwargs, timeout)
            entry.calls += 1
            entry.last_error = None
            return {
                "success": True, "tool": entry.name, "output": self._serialize(output),
                "error": None, "duration_ms": (time.perf_counter() - start) * 1000.0,
            }
        except asyncio.TimeoutError:
            entry.last_error = f"timeout tras {timeout}s"
            entry.calls += 1
            return {
                "success": False, "tool": entry.name, "output": None,
                "error": f"timeout tras {timeout}s",
                "duration_ms": (time.perf_counter() - start) * 1000.0,
            }
        except Exception as exc:  # noqa: BLE001
            entry.last_error = str(exc)
            entry.calls += 1
            return {
                "success": False, "tool": entry.name, "output": None,
                "error": str(exc), "duration_ms": (time.perf_counter() - start) * 1000.0,
            }

    @staticmethod
    def _serialize(value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)


class DynamicToolRegistry:
    """Registro dinamico y cargador de herramientas/habilidades locales."""

    def __init__(self, scripts_dir: Optional[str] = None, auto_scan: bool = True) -> None:
        base = scripts_dir or str((Path(__file__).parent / "tools"))
        self.scripts_dir = Path(base)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, ToolEntry] = {}
        self._audit: List[Dict[str, Any]] = []
        self._audit_max = 200
        self.sandbox = SkillExecutionSandbox(self)
        if auto_scan:
            self.scan()

    def _load_module_file(self, path: Path) -> Optional[ModuleType]:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            logger.warning("No se pudo cargar skill '%s': %s", path.name, exc)
            return None

    def _register_module(self, module: ModuleType, path: Path) -> int:
        manifest = getattr(module, "TOOLS", None)
        count = 0
        if isinstance(manifest, dict):
            # El nombre puede venir como clave del dict o dentro del propio entry.
            items = [(key, raw) for key, raw in manifest.items()]
        elif isinstance(manifest, list):
            items = [(None, raw) for raw in manifest]
        else:
            items = []
        for key, raw in items:
            if not isinstance(raw, dict) or not callable(raw.get("func")):
                continue
            name = str(raw.get("name") or key or "").strip()
            if not name:
                continue
            self._entries[name] = ToolEntry(
                name=name,
                description=str(raw.get("description", "")),
                parameters=dict(raw.get("parameters", {}) or {}),
                func=raw["func"],
                category=str(raw.get("category", "custom")),
                risk=str(raw.get("risk", "safe")),
                module=path.name,
                source="module",
            )
            count += 1
        self._log("scan", {"module": path.name, "registered": count})
        return count

    def scan(self) -> int:
        """Escanea el directorio de skills y registra cada modulo valido."""
        total = 0
        for f in sorted(self.scripts_dir.glob("*.py")):
            if f.name.startswith("_") or f.name == "__init__.py":
                continue
            module = self._load_module_file(f)
            if module is not None:
                total += self._register_module(module, f)
        self._log("scan_end", {"total": total})
        return total

    def load_from_path(self, path: str) -> int:
        """Carga y registra un modulo de skill por ruta (validada dentro del dir)."""
        p = (self.scripts_dir / path).resolve()
        if self.scripts_dir.resolve() not in p.parents:
            raise ValueError(f"ruta fuera del directorio de skills: {path}")
        if not p.exists() or p.suffix != ".py":
            raise ValueError(f"skill no encontrada: {path}")
        module = self._load_module_file(p)
        if module is None:
            return 0
        return self._register_module(module, p)

    def register_callable(
        self,
        name: str,
        func: Callable[..., Any],
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        category: str = "custom",
        risk: str = "safe",
    ) -> ToolEntry:
        entry = ToolEntry(
            name=name,
            description=description or "",
            parameters=parameters or {"type": "object", "properties": {}, "required": []},
            func=func,
            category=category,
            risk=risk,
            source="manual",
        )
        self._entries[name] = entry
        self._log("register", {"tool": name, "category": category})
        return entry

    def unregister(self, name: str) -> bool:
        if name in self._entries:
            del self._entries[name]
            self._log("unregister", {"tool": name})
            return True
        return False

    def get(self, name: str) -> Optional[ToolEntry]:
        return self._entries.get(name)

    def has(self, name: str) -> bool:
        return name in self._entries

    def list_tools(self) -> List[Dict[str, Any]]:
        tools = [e.to_dict() for e in self._entries.values()]
        return sorted(tools, key=lambda t: t["name"])

    def function_schemas(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Esquemas de function-calling a inyectar al modelo local (Jan/Ollama)."""
        entries = self._entries.values()
        if category:
            entries = [e for e in entries if e.category == category]
        return [e.to_function_schema() for e in sorted(entries, key=lambda x: x.name)]

    def audit(self) -> Dict[str, Any]:
        return {
            "scripts_dir": str(self.scripts_dir),
            "tools_total": len(self._entries),
            "tools": self.list_tools(),
            "rate_limit": {
                "limit": TOOL_RATE_LIMIT,
                "window_s": TOOL_RATE_WINDOW,
                "rejected": self.sandbox.rate_limit_state(),
            },
            "recent_events": list(self._audit[-20:]),
        }

    async def execute_tool(self, name: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        entry = self._entries.get(name)
        if not entry:
            return {"success": False, "tool": name, "output": None, "error": f"unknown tool: {name}", "duration_ms": 0.0}

        # Permission check (fail-closed)
        if get_permission_engine:
            try:
                engine = get_permission_engine()
                allowed, reason, request_id = engine.check(name, entry.risk, params)
                if not allowed:
                    if request_id:
                        # ASK mode: wait for human approval
                        self._log("permission_ask", {"tool": name, "request_id": request_id, "reason": reason})
                        approved, deny_reason = engine.wait_for_approval(request_id, timeout=min(timeout, 120.0))
                        if not approved:
                            self._log("permission_denied", {"tool": name, "request_id": request_id, "reason": deny_reason})
                            return {
                                "success": False, "tool": name, "output": None,
                                "error": f"permission denied: {deny_reason}", "duration_ms": 0.0,
                            }
                        # Approved - verify args hash still matches (single-use)
                        if not engine.verify_args_hash(request_id, params):
                            self._log("permission_denied", {"tool": name, "request_id": request_id, "reason": "args mismatch after approval"})
                            return {
                                "success": False, "tool": name, "output": None,
                                "error": "permission denied: arguments changed after approval", "duration_ms": 0.0,
                            }
                    else:
                        # Hard deny
                        self._log("permission_denied", {"tool": name, "reason": reason})
                        return {
                            "success": False, "tool": name, "output": None,
                            "error": f"permission denied: {reason}", "duration_ms": 0.0,
                        }
            except Exception as exc:
                logger.warning("Permission check failed for %s: %s", name, exc)
                # Fail-closed: deny on permission system failure
                return {
                    "success": False, "tool": name, "output": None,
                    "error": f"permission system error: {exc}", "duration_ms": 0.0,
                }

        return await self.sandbox.execute(entry, params, timeout)

    def _log(self, event: str, payload: Dict[str, Any]) -> None:
        self._audit.append({"event": event, "payload": payload, "ts": time.time()})
        if len(self._audit) > self._audit_max:
            self._audit = self._audit[-self._audit_max:]


_registry_instance: Optional[DynamicToolRegistry] = None


def get_tools_registry(scripts_dir: Optional[str] = None) -> DynamicToolRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = DynamicToolRegistry(scripts_dir=scripts_dir)
    return _registry_instance


def reset_tools_registry() -> None:
    global _registry_instance
    _registry_instance = None


tool_registry = get_tools_registry()

tool_registry.scan()
