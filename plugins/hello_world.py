"""AURA Plugin Example — Hello World plugin."""

from __future__ import annotations

from aura_plugin_system import AuraPlugin


class HelloWorldPlugin(AuraPlugin):
    def get_name(self) -> str:
        return "Hello World"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Simple hello world plugin example"
    
    def on_load(self) -> None:
        print(f"[PLUGIN] {self.get_name()} loaded!")
    
    def on_chat_message(self, message: str) -> str:
        if "hello" in message.lower():
            return "Hello from plugin!"
        return None
