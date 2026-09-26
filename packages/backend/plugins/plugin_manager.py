import importlib.util
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yaml
import asyncio
import time
import json
from datetime import datetime


class PluginManager:
    """Sistema de plugins extensible para AURA OS v2.

    Gestiona el ciclo de completo de plugins:
    - Carga dinamica desde backend/plugins/{plugin_name}/
    - Validacion de estructura (metadata, commands, dependencies)
    - Registro en agent_registry automatico
    - Soporte para reload y unload
    """

    def __init__(self, plugins_dir: str = "backend/plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, Any] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self.plugin_metadata: Dict[str, Dict] = {}
        self.plugin_agents: Dict[str, Any] = {}
        self.commands: Dict[str, Dict[str, Any]] = {}
        self._loaded_plugins: Dict[str, Dict] = {}
        self._startup_hooks: List[Callable] = []
        self._shutdown_hooks: List[Callable] = []
        self._chat_hooks: List[Callable] = []
        self._skill_hooks: List[Callable] = []
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    def _load_all_plugins(self) -> None:
        print(f"[PluginManager] Cargando plugins desde {self.plugins_dir}")
        if not self.plugins_dir.exists():
            print(f"[PluginManager] Directorio no existe: {self.plugins_dir}")
            return
        for plugin_file in self.plugins_dir.rglob("*.py"):
            if plugin_file.name.startswith("_") or plugin_file.name.startswith("."):
                continue
            if "template" in str(plugin_file):
                continue
            try:
                self._load_plugin_file(plugin_file)
            except Exception as e:
                print(f"[PluginManager] Error loading {plugin_file.name}: {e}")

    def _load_plugin_file(self, plugin_file: Path) -> None:
        spec = importlib.util.spec_from_file_location(
            f"backend.plugins.{plugin_file.stem}",
            plugin_file,
        )
        if not spec or not spec.loader:
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "Plugin"):
            try:
                plugin_instance = module.Plugin()
                plugin_name = plugin_file.stem
                self.plugins[plugin_name] = plugin_instance
                self.plugin_metadata[plugin_name] = {
                    "name": getattr(plugin_instance, "name", plugin_name),
                    "version": getattr(plugin_instance, "version", "1.0.0"),
                    "description": getattr(plugin_instance, "description", ""),
                    "file": str(plugin_file),
                    "loaded_at": datetime.now().isoformat(),
                }
                if hasattr(plugin_instance, "get_hooks"):
                    hooks = plugin_instance.get_hooks()
                    for hook_name, hook_func in hooks.items():
                        if hook_name not in self.hooks:
                            self.hooks[hook_name] = []
                        self.hooks[hook_name].append(hook_func)
                        print(f"[PluginManager] Registered hook '{hook_name}' from {plugin_name}")
                if hasattr(plugin_instance, "on_load"):
                    plugin_instance.on_load()
                print(f"[PluginManager] Plugin '{plugin_name}' loaded successfully")
            except Exception as e:
                print(f"[PluginManager] Error instantiating plugin: {e}")

    def load_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Carga un plugin por nombre desde su directorio."""
        plugin_path = self.plugins_dir / plugin_name
        if not plugin_path.exists():
            return {"status": "error", "error": f"Plugin '{plugin_name}' not found", "plugin": None}

        yaml_path = plugin_path / "plugin.yaml"
        if not yaml_path.exists():
            return {"status": "error", "error": f"plugin.yaml not found in '{plugin_name}'", "plugin": None}

        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)
        except Exception as e:
            return {"status": "error", "error": f"Failed to parse plugin.yaml: {e}", "plugin": None}

        if not metadata or "name" not in metadata:
            return {"status": "error", "error": "Invalid plugin.yaml: missing 'name'", "plugin": None}

        if plugin_name in self.plugins:
            return {"status": "error", "error": f"Plugin '{plugin_name}' already loaded", "plugin": None}

        agent_module_path = plugin_path / "agent.py"
        if not agent_module_path.exists():
            return {"status": "error", "error": f"agent.py not found in '{plugin_name}'", "plugin": None}

        try:
            spec = importlib.util.spec_from_file_location(
                f"backend.plugins.{plugin_name}.agent",
                agent_module_path,
            )
            if not spec or not spec.loader:
                return {"status": "error", "error": f"Failed to load agent.py", "plugin": None}
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            agent_class = getattr(module, "PluginAgent", None)
            if agent_class is None:
                return {"status": "error", "error": "No PluginAgent class found", "plugin": None}

            agent_instance = agent_class()
            agent_instance.name = metadata.get("name", plugin_name)
            agent_instance.version = metadata.get("version", "1.0.0")

            self.plugin_agents[plugin_name] = agent_instance
            self.plugin_metadata[plugin_name] = metadata
            self.plugins[plugin_name] = plugin_path
            self._loaded_plugins[plugin_name] = {
                "name": metadata.get("name", plugin_name),
                "version": metadata.get("version", "1.0.0"),
                "author": metadata.get("author", "AURA"),
                "description": metadata.get("description", ""),
                "status": "loaded",
                "commands": [cmd.get("name", "") for cmd in metadata.get("commands", [])],
                "dependencies": metadata.get("dependencies", []),
                "capabilities": metadata.get("capabilities", []),
                "settings": metadata.get("settings", {}),
                "loaded_at": datetime.now().isoformat(),
            }

            if hasattr(agent_instance, "on_load"):
                if asyncio.iscoroutinefunction(agent_instance.on_load):
                    asyncio.run(agent_instance.on_load())
                else:
                    agent_instance.on_load()

            for cmd in metadata.get("commands", []):
                cmd_name = cmd.get("name", "")
                if cmd_name:
                    self.commands[cmd_name] = {
                        "plugin": plugin_name,
                        "params": cmd.get("params", []),
                        "async": cmd.get("async", False),
                    }

            self._register_agent_in_registry(plugin_name, metadata)

            return {"status": "loaded", "plugin": self._loaded_plugins[plugin_name]}
        except Exception as e:
            return {"status": "error", "error": str(e), "plugin": None}

    def _register_agent_in_registry(self, plugin_name: str, metadata: Dict) -> None:
        """Registra el plugin como agente en el registry global."""
        try:
            from backend.core.agent_registry_v2 import AgentRegistryV2
            registry = AgentRegistryV2()
            config = {
                "name": metadata.get("name", plugin_name),
                "type": "plugin",
                "description": metadata.get("description", ""),
                "commands": [cmd.get("name", "") for cmd in metadata.get("commands", [])],
                "capabilities": metadata.get("capabilities", []),
                "settings": metadata.get("settings", {}),
            }
            registry.register_agent(config)
            print(f"[PluginManager] Registered '{plugin_name}' in agent registry")
        except Exception as e:
            print(f"[PluginManager] Could not register in agent registry: {e}")

    def unload_plugin(self, plugin_name: str) -> Dict[str, str]:
        """Descarga un plugin y limpia todos sus recursos."""
        if plugin_name not in self.plugins:
            return {"status": "error", "error": f"Plugin '{plugin_name}' not loaded"}

        agent = self.plugin_agents.get(plugin_name)
        if agent and hasattr(agent, "on_unload"):
            try:
                if asyncio.iscoroutinefunction(agent.on_unload):
                    asyncio.run(agent.on_unload())
                else:
                    agent.on_unload()
            except Exception as e:
                return {"status": "error", "error": f"Error in on_unload: {e}"}

        metadata = self.plugin_metadata.get(plugin_name, {})
        for cmd in metadata.get("commands", []):
            cmd_name = cmd.get("name", "")
            if cmd_name in self.commands:
                del self.commands[cmd_name]

        for hook_list in [self._startup_hooks, self._shutdown_hooks, self._chat_hooks, self._skill_hooks]:
            hook_list[:] = [h for h in hook_list if not getattr(h, "__plugin__", None) == plugin_name]

        del self.plugins[plugin_name]
        del self.plugin_metadata[plugin_name]
        del self.plugin_agents[plugin_name]
        del self._loaded_plugins[plugin_name]

        try:
            from backend.core.agent_registry_v2 import AgentRegistryV2
            registry = AgentRegistryV2()
            for aid in list(registry._agents.keys()):
                if registry._agents[aid].get("name") == plugin_name:
                    del registry._agents[aid]
                    del registry._configs[aid]
                    if aid in registry._endpoints:
                        del registry._endpoints[aid]
            registry._save()
        except Exception:
            pass

        print(f"[PluginManager] Plugin '{plugin_name}' unloaded")
        return {"status": "unloaded"}

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Retorna lista de todos los plugins cargados."""
        result = []
        for name, meta in self._loaded_plugins.items():
            result.append({
                "name": meta.get("name", name),
                "version": meta.get("version", "1.0.0"),
                "status": meta.get("status", "loaded"),
                "commands": meta.get("commands", []),
                "description": meta.get("description", ""),
            })
        return result

    def reload_all_plugins(self) -> Dict[str, Any]:
        """Recarga todos los plugins utiles para desarrollo."""
        plugin_names = list(self._loaded_plugins.keys())
        reloaded = []
        errors = []
        for name in plugin_names:
            self.unload_plugin(name)
            result = self.load_plugin(name)
            if result.get("status") == "loaded":
                reloaded.append(name)
            else:
                errors.append({"plugin": name, "error": result.get("error")})
        return {"status": "reloaded", "reloaded": reloaded, "errors": errors, "total": len(plugin_names)}

    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Ejecuta un hook sincronicamente."""
        results = []
        if hook_name not in self.hooks:
            return results
        for hook_func in self.hooks[hook_name]:
            try:
                result = hook_func(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"[PluginManager] Error executing hook '{hook_name}': {e}")
        return results

    async def execute_hook_async(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Ejecuta un hook asincronicamente."""
        results = []
        if hook_name not in self.hooks:
            return results
        for hook_func in self.hooks[hook_name]:
            try:
                if asyncio.iscoroutinefunction(hook_func):
                    result = await hook_func(*args, **kwargs)
                else:
                    result = hook_func(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"[PluginManager] Error executing async hook '{hook_name}': {e}")
        return results

    def register_custom_skill(self, skill_name: str, skill_func: Callable) -> None:
        """Registra una skill personalizada en el registry global."""
        try:
            from backend.skills.registry import registry
            registry.register_skill(skill_name, skill_func)
            print(f"[PluginManager] Skill '{skill_name}' registered from plugin")
        except Exception as e:
            print(f"[PluginManager] Error registering skill: {e}")

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        return self.plugins.get(plugin_name)


plugin_manager = PluginManager()
