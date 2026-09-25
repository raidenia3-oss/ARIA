from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

from backend.plugins.manager import PluginManager, plugin_manager

__all__ = ["PluginManager", "plugin_manager"]
