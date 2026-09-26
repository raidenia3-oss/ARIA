from backend.plugins.plugin_manager import PluginManager, plugin_manager

__all__ = ["PluginManager", "plugin_manager"]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
