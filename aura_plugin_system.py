"""AURA Plugin System — extensible architecture for custom modules.

Plugins can add new tabs, commands, AI providers, or integrations.

Usage:
    from aura_plugin_system import PluginManager, AuraPlugin
    
    class MyPlugin(AuraPlugin):
        def get_name(self): return "My Plugin"
        def get_tab(self): return my_tab_frame
        def on_load(self): print("Plugin loaded")
    
    manager = PluginManager()
    manager.register(MyPlugin())
    manager.load_all()
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


class AuraPlugin:
    """Base class for all AURA plugins."""
    
    def get_name(self) -> str:
        return "Unnamed Plugin"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return ""
    
    def get_author(self) -> str:
        return "Unknown"
    
    def get_tab(self) -> Optional[Any]:
        return None
    
    def get_commands(self) -> Dict[str, Any]:
        return {}
    
    def on_load(self) -> None:
        pass
    
    def on_unload(self) -> None:
        pass
    
    def on_chat_message(self, message: str) -> Optional[str]:
        return None
    
    def on_voice_command(self, command: str) -> Optional[Dict[str, Any]]:
        return None
    
    def on_gesture(self, gesture: str, confidence: float) -> Optional[Dict[str, Any]]:
        return None


class PluginManager:
    def __init__(self, plugins_dir: Optional[Path] = None) -> None:
        self.plugins_dir = plugins_dir or Path(__file__).resolve().parent / "plugins"
        self.plugins: Dict[str, AuraPlugin] = {}
        self._load_order: List[str] = []
        self._hooks: Dict[str, List[Any]] = {
            "on_chat": [],
            "on_voice": [],
            "on_gesture": [],
            "on_vision": [],
            "on_service_start": [],
            "on_service_stop": [],
            "on_training_start": [],
            "on_training_complete": [],
        }
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        config_path = self.plugins_dir / "config.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"plugins": [], "settings": {"auto_load_plugins": True, "plugin_directory": "plugins", "allow_unknown_plugins": False}}

    def _is_plugin_enabled(self, name: str) -> bool:
        plugin_configs = self._config.get("plugins", [])
        if plugin_configs:
            for plugin_config in plugin_configs:
                if plugin_config.get("name") == name:
                    return plugin_config.get("enabled", True)
            return False
        return self._config.get("settings", {}).get("allow_unknown_plugins", True)

    def register(self, plugin: AuraPlugin) -> None:
        name = plugin.get_name()
        self.plugins[name] = plugin
        self._load_order.append(name)

    def load_from_directory(self) -> List[str]:
        loaded = []
        if not self.plugins_dir.exists():
            return loaded
        for py_file in self.plugins_dir.glob("*.py"):
            if py_file.stem.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[py_file.stem] = module
                    spec.loader.exec_module(module)
                    for attr in dir(module):
                        obj = getattr(module, attr)
                        if isinstance(obj, type) and issubclass(obj, AuraPlugin) and obj != AuraPlugin:
                            instance = obj()
                            name = instance.get_name()
                            if self._is_plugin_enabled(name):
                                self.register(instance)
                                loaded.append(name)
            except Exception:
                continue
        return loaded

    def load_all(self) -> None:
        for name in self._load_order:
            plugin = self.plugins[name]
            try:
                plugin.on_load()
            except Exception:
                pass

    def unload_all(self) -> None:
        for name in reversed(self._load_order):
            plugin = self.plugins[name]
            try:
                plugin.on_unload()
            except Exception:
                pass

    def get_plugin(self, name: str) -> Optional[AuraPlugin]:
        return self.plugins.get(name)

    def get_all_plugins(self) -> List[AuraPlugin]:
        return list(self.plugins.values())

    def get_tabs(self) -> Dict[str, Any]:
        tabs = {}
        for name, plugin in self.plugins.items():
            tab = plugin.get_tab()
            if tab is not None:
                tabs[name] = tab
        return tabs

    def get_commands(self) -> Dict[str, Any]:
        commands = {}
        for plugin in self.plugins.values():
            commands.update(plugin.get_commands())
        return commands

    def hook(self, event: str, callback: Any) -> None:
        if event in self._hooks:
            self._hooks[event].append(callback)

    def trigger(self, event: str, *args: Any, **kwargs: Any) -> None:
        if event in self._hooks:
            for cb in self._hooks[event]:
                try:
                    cb(*args, **kwargs)
                except Exception:
                    pass

    def on_chat_message(self, message: str) -> Optional[str]:
        for plugin in self.plugins.values():
            try:
                result = plugin.on_chat_message(message)
                if result:
                    return result
            except Exception:
                continue
        return None

    def on_voice_command(self, command: str) -> Optional[Dict[str, Any]]:
        for plugin in self.plugins.values():
            try:
                result = plugin.on_voice_command(command)
                if result:
                    return result
            except Exception:
                continue
        return None

    def on_gesture(self, gesture: str, confidence: float) -> Optional[Dict[str, Any]]:
        for plugin in self.plugins.values():
            try:
                result = plugin.on_gesture(gesture, confidence)
                if result:
                    return result
            except Exception:
                continue
        return None
