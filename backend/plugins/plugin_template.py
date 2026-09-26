"""PluginAgent base class for AURA OS dynamic plugin system.

All agents/plugins should inherit from this class and override
the lifecycle methods and command handlers as needed.

Usage:
    class MyPlugin(PluginAgent):
        def __init__(self):
            super().__init__()
            self.name = "my-plugin"
            self.version = "1.0.0"
            self.commands = {"mycmd": self.mycmd}

        async def on_load(self):
            # initialization code
            pass

        async def on_unload(self):
            # cleanup code
            pass
"""
import asyncio
from typing import Any, Dict, Optional


class PluginAgent:
    """Base class for all AURA plugins and agents.

    Provides lifecycle management (on_load/on_unload) and
    command execution infrastructure.
    """

    def __init__(self):
        self.name: str = ""
        self.version: str = "1.0.0"
        self.commands: Dict[str, Callable] = {}
        self._initialized: bool = False
        self._created_at: Optional[float] = None

    async def on_load(self) -> None:
        """Se ejecuta cuando se carga el plugin.

        Sobreescribe este metodo para inicializar recursos,
        conectar a servicios externos, o registrar hooks.
        """
        self._initialized = True
        pass

    async def on_unload(self) -> None:
        """Se ejecuta cuando se descarga el plugin.

        Sobreescribe este metodo para liberar recursos,
        cerrar conexiones, o persistir estado.
        """
        self._initialized = False
        pass

    async def execute(self, command: str, args: dict) -> dict:
        """Ejecuta comando del plugin.

        Args:
            command: Nombre del comando a ejecutar.
            args: Argumentos del comando como diccionario.

        Returns:
            dict con el resultado de la ejecucion o error.
        """
        if command in self.commands:
            handler = self.commands[command]
            if asyncio.iscoroutinefunction(handler):
                return asyncio.run(handler(args)) if not asyncio.get_event_loop().is_running() else await handler(args)
            return handler(args)
        return {"error": f"Command '{command}' not found", "available": list(self.commands.keys())}

    def get_info(self) -> dict:
        """Retorna informacion basica del plugin."""
        return {
            "name": self.name,
            "version": self.version,
            "commands": list(self.commands.keys()),
            "initialized": self._initialized,
        }
