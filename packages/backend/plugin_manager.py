"""Plugin manager for AURA - Module 29.

Carga e integracion dinamica de plugins externos (modulos .py o paquetes),
sandbox de ejecucion segura, hooks de lifecycle y registro de plugins.
"""

from __future__ import annotations

import importlib.util
import os
import time
import types
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

ALLOWED_MODULES: List[str] = [
    "json", "math", "re", "datetime", "time", "collections",
    "itertools", "functools", "typing", "statistics", "hashlib",
]

SAFE_BUILTINS: Dict[str, Any] = {
    "len": len, "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "tuple": tuple, "set": set, "range": range,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "sum": sum, "min": min, "max": max, "sorted": sorted, "reversed": reversed,
    "abs": abs, "round": round, "isinstance": isinstance, "hasattr": hasattr,
    "getattr": getattr, "print": print, "Exception": Exception,
    "ValueError": ValueError, "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "StopIteration": StopIteration,
    "True": True, "False": False, "None": None,
}

HOOK_LIFECYCLE_TYPES: List[str] = ["pre_exec", "post_exec", "event"]


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = "unknown"
    entry_point: str = "plugin_execute"
    hooks: List[str] = field(default_factory=list)
    enabled: bool = True
    loaded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    manifest_path: str = ""
    module_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "description": self.description, "author": self.author,
            "entry_point": self.entry_point, "hooks": self.hooks,
            "enabled": self.enabled, "loaded_at": self.loaded_at,
            "manifest_path": self.manifest_path,
        }


class PluginSandbox:
    """Sandbox de ejecucion segura para plugins."""

    def __init__(self, plugin_id: str, module: Optional[types.ModuleType] = None) -> None:
        self.plugin_id = plugin_id
        self.module = module
        self.allowed_modules = set(ALLOWED_MODULES)
        self.execution_log: List[Dict[str, Any]] = []

    def execute_function(self, func_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if self.module is None:
            return {"executed": False, "error": "no_module_loaded"}
        func = getattr(self.module, func_name, None)
        if func is None or not callable(func):
            return {"executed": False, "error": f"function_not_found: {func_name}"}
        entry = {"func": func_name, "executed_at": datetime.utcnow().isoformat() + "Z", "success": False}
        try:
            result = func(context)
            entry["success"] = True
            entry["result"] = result
        except Exception as exc:
            entry["error"] = str(exc)
        self.execution_log.append(entry)
        return entry

    def execute_code(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        safe_globals = self._safe_globals()
        local_vars: Dict[str, Any] = {"context": context, "result": None}
        entry = {"executed_at": datetime.utcnow().isoformat() + "Z", "success": False}
        try:
            exec(code, safe_globals, local_vars)
            entry["success"] = True
            entry["result"] = local_vars.get("result")
        except Exception as exc:
            entry["error"] = str(exc)
        self.execution_log.append(entry)
        return entry

    def _safe_globals(self) -> Dict[str, Any]:
        import importlib
        safe_globals: Dict[str, Any] = {
            "__builtins__": dict(SAFE_BUILTINS),
            "__name__": f"plugin_{self.plugin_id}",
            "json": json,
            "math": math,
            "re": re,
            "datetime": datetime,
            "time": time,
            "hashlib": hashlib,
        }
        for mod_name in self.allowed_modules:
            try:
                safe_globals[mod_name] = importlib.import_module(mod_name)
            except ImportError:
                pass
        return safe_globals

    def get_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.execution_log[-limit:]


class HookLifecycleManager:
    """Gestiona hooks de lifecycle: pre_exec, post_exec, event-listeners."""

    def __init__(self) -> None:
        self.hooks: Dict[str, List[Tuple[str, Callable[..., Any]]]] = {}

    def register_hook(self, hook_type: str, name: str, func: Callable[..., Any]) -> None:
        if hook_type not in self.hooks:
            self.hooks[hook_type] = []
        self.hooks[hook_type].append((name, func))

    def trigger_hooks(self, hook_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        hooks = self.hooks.get(hook_type, [])
        results: List[Dict[str, Any]] = []
        for name, func in hooks:
            entry: Dict[str, Any] = {"hook": name, "hook_type": hook_type, "success": False}
            try:
                result = func(context)
                entry["success"] = True
                entry["result"] = result
            except Exception as exc:
                entry["error"] = str(exc)
            results.append(entry)
        return results

    def remove_hook(self, hook_type: str, name: str) -> bool:
        if hook_type in self.hooks:
            before = len(self.hooks[hook_type])
            self.hooks[hook_type] = [(n, f) for n, f in self.hooks[hook_type] if n != name]
            return len(self.hooks[hook_type]) < before
        return False

    def list_hooks(self) -> Dict[str, List[str]]:
        return {htype: [name for name, _ in funcs] for htype, funcs in self.hooks.items()}


class PluginManager:
    """Cargador y gestor de plugins externos."""

    def __init__(self, plugins_dir: Optional[str] = None) -> None:
        self.plugins: Dict[str, types.ModuleType] = {}
        self.manifests: Dict[str, PluginManifest] = {}
        self.sandboxes: Dict[str, PluginSandbox] = {}
        self.hooks = HookLifecycleManager()
        self.plugins_dir = plugins_dir or os.path.join(os.getcwd(), "plugins")
        self._load_bundled_plugins()

    def _load_bundled_plugins(self) -> None:
        if not os.path.isdir(self.plugins_dir):
            return
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                filepath = os.path.join(self.plugins_dir, filename)
                try:
                    self.load_plugin(filepath)
                except Exception:
                    pass

    def load_plugin(self, filepath: str, manifest_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            return {"status": "error", "error": "file_not_found"}

        module_name = f"plugin_{os.path.splitext(os.path.basename(filepath))[0]}_{int(time.time())}"
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return {"status": "error", "error": "invalid_plugin_file"}

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            return {"status": "error", "error": f"plugin_load_failed: {exc}"}

        manifest_dict = getattr(module, "PLUGIN_MANIFEST", {})
        if manifest_override:
            manifest_dict.update(manifest_override)

        plugin_id = manifest_dict.get("id") or f"plugin_{os.path.splitext(os.path.basename(filepath))[0]}"
        manifest = PluginManifest(
            id=str(plugin_id),
            name=manifest_dict.get("name", os.path.basename(filepath)),
            version=str(manifest_dict.get("version", "1.0.0")),
            description=str(manifest_dict.get("description", "")),
            author=str(manifest_dict.get("author", "unknown")),
            entry_point=str(manifest_dict.get("entry_point", "plugin_execute")),
            hooks=list(manifest_dict.get("hooks", [])),
            manifest_path=filepath,
            module_name=module_name,
        )

        self.plugins[plugin_id] = module
        self.manifests[plugin_id] = manifest
        self.sandboxes[plugin_id] = PluginSandbox(plugin_id, module)
        self._register_hooks(plugin_id)

        return {"status": "loaded", "plugin_id": str(plugin_id), "manifest": manifest.to_dict()}

    def register_plugin(
        self,
        manifest_data: Dict[str, Any],
        code: str,
    ) -> Dict[str, Any]:
        plugin_id = str(manifest_data.get("id", f"plugin_{int(time.time() * 1000000)}"))
        module_name = f"plugin_{plugin_id.replace('-', '_')}"

        module = types.ModuleType(module_name)
        module.__dict__["__file__"] = f"<inline:{plugin_id}>"
        sandbox = PluginSandbox(plugin_id, None)
        exec_result = sandbox.execute_code(code, {})
        if not exec_result["success"]:
            return {"status": "error", "error": exec_result.get("error", "code_execution_failed")}

        for key, value in exec_result.get("result", {}).items() if isinstance(exec_result.get("result"), dict) else []:
            setattr(module, key, value)

        manifest = PluginManifest(
            id=plugin_id,
            name=manifest_data.get("name", plugin_id),
            version=str(manifest_data.get("version", "1.0.0")),
            description=str(manifest_data.get("description", "")),
            author=str(manifest_data.get("author", "unknown")),
            entry_point=str(manifest_data.get("entry_point", "plugin_execute")),
            hooks=list(manifest_data.get("hooks", [])),
        )

        self.plugins[plugin_id] = module
        self.manifests[plugin_id] = manifest
        self.sandboxes[plugin_id] = PluginSandbox(plugin_id, module)
        self._register_hooks(plugin_id)

        return {"status": "registered", "plugin_id": plugin_id, "manifest": manifest.to_dict()}

    def _register_hooks(self, plugin_id: str) -> None:
        manifest = self.manifests[plugin_id]
        module = self.plugins.get(plugin_id)
        if module is None:
            return
        for hook_type in manifest.hooks:
            func = getattr(module, f"on_{hook_type}", None)
            if callable(func):
                self.hooks.register_hook(hook_type, plugin_id, func)

    def unregister_plugin(self, plugin_id: str) -> Dict[str, Any]:
        if plugin_id not in self.plugins:
            return {"status": "error", "error": "plugin_not_found"}
        for hook_type in list(self.hooks.hooks.keys()):
            self.hooks.remove_hook(hook_type, plugin_id)
        del self.plugins[plugin_id]
        del self.manifests[plugin_id]
        del self.sandboxes[plugin_id]
        return {"status": "unregistered", "plugin_id": plugin_id}

    def toggle_plugin(self, plugin_id: str) -> Dict[str, Any]:
        if plugin_id not in self.manifests:
            return {"status": "error", "error": "plugin_not_found"}
        self.manifests[plugin_id].enabled = not self.manifests[plugin_id].enabled
        return {
            "status": "toggled",
            "plugin_id": plugin_id,
            "enabled": self.manifests[plugin_id].enabled,
        }

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self.manifests.values()]

    def execute_plugin(self, plugin_id: str, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if plugin_id not in self.sandboxes:
            return {"error": "plugin_not_found"}
        manifest = self.manifests[plugin_id]
        if not manifest.enabled:
            return {"error": "plugin_disabled"}

        pre_results = self.hooks.trigger_hooks("pre_exec", context)
        exec_result = self.sandboxes[plugin_id].execute_function(hook_type, context)
        post_results = self.hooks.trigger_hooks("post_exec", {**context, "result": exec_result})

        return {
            "plugin_id": plugin_id,
            "hook_type": hook_type,
            "pre_exec_hooks": pre_results,
            "execution": exec_result,
            "post_exec_hooks": post_results,
        }

    def trigger_event(self, event_type: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self.hooks.trigger_hooks(event_type, context)
