import importlib.util
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class PluginManager:
    """Sistema de plugins extensible para AURA"""

    def __init__(self, plugins_dir: str = "backend/plugins/custom"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins: Dict[str, Any] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self.plugin_metadata: Dict[str, Dict] = {}

        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.load_all_plugins()

    def load_all_plugins(self) -> None:
        print(f"[PluginManager] Cargando plugins desde {self.plugins_dir}")

        if not self.plugins_dir.exists():
            print(f"[PluginManager] Directorio no existe: {self.plugins_dir}")
            return

        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("_") or plugin_file.name.startswith("."):
                continue
            try:
                self._load_plugin_file(plugin_file)
            except Exception as e:
                print(f"[PluginManager] Error loading {plugin_file.name}: {e}")

    def _load_plugin_file(self, plugin_file: Path) -> None:
        spec = importlib.util.spec_from_file_location(
            plugin_file.stem,
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

    def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
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
        import asyncio

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
        try:
            from backend.skills.registry import registry

            registry.register_skill(skill_name, skill_func)
            print(f"[PluginManager] Skill '{skill_name}' registered from plugin")
        except Exception as e:
            print(f"[PluginManager] Error registering skill: {e}")

    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        return self.plugins.get(plugin_name)

    def list_plugins(self) -> Dict[str, Dict]:
        result = {}
        for name, plugin in self.plugins.items():
            entry = dict(self.plugin_metadata.get(name, {}))
            plugin_hooks = plugin.get_hooks() if hasattr(plugin, "get_hooks") else {}
            entry["hooks"] = list(plugin_hooks.keys())
            result[name] = entry
        return result

    def unload_plugin(self, plugin_name: str) -> bool:
        if plugin_name not in self.plugins:
            return False

        plugin = self.plugins[plugin_name]

        if hasattr(plugin, "on_unload"):
            try:
                plugin.on_unload()
            except Exception as e:
                print(f"[PluginManager] Error in on_unload: {e}")

        plugin_hooks = plugin.get_hooks() if hasattr(plugin, "get_hooks") else {}
        for hook_name, hook_func in plugin_hooks.items():
            if hook_name in self.hooks:
                self.hooks[hook_name] = [h for h in self.hooks[hook_name] if h != hook_func]

        del self.plugins[plugin_name]
        del self.plugin_metadata[plugin_name]

        print(f"[PluginManager] Plugin '{plugin_name}' unloaded")
        return True


plugin_manager = PluginManager()
