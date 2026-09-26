from datetime import datetime


class Plugin:
    """Plugin de ejemplo para AURA"""

    def __init__(self):
        self.name = "Example Plugin"
        self.version = "1.0.0"
        self.description = "Plugin de ejemplo que muestra hooks basicos"
        self.execution_count = 0

    def on_load(self):
        print(f"[{self.name}] Plugin cargado exitosamente")

    def on_unload(self):
        print(f"[{self.name}] Plugin descargado")

    def get_hooks(self):
        return {
            "on_startup": self.on_startup,
            "on_chat": self.on_chat,
            "on_skill_execute": self.on_skill_execute,
            "on_shutdown": self.on_shutdown,
        }

    def on_startup(self):
        print(f"[{self.name}] AURA iniciado")

    def on_chat(self, message: str, metadata: dict = None):
        self.execution_count += 1
        print(f"[{self.name}] Chat #{self.execution_count}: {message[:50]}...")
        return {
            "plugin": self.name,
            "action": "logged_message",
            "timestamp": datetime.now().isoformat(),
        }

    def on_skill_execute(self, skill_name: str, args: dict = None):
        print(f"[{self.name}] Ejecutando skill: {skill_name}")
        return {
            "plugin": self.name,
            "skill": skill_name,
            "args": args,
        }

    def on_shutdown(self):
        print(f"[{self.name}] AURA apagandose ( ejecuto {self.execution_count} acciones )")
