"""Configuration — Configuración runtime"""

from typing import Dict


class ConfigManager:
    """Gestión de configuración"""

    def __init__(self):
        self.config: Dict = {
            'app': {'name': 'ARIA OS', 'version': '4.0.0'},
            'ai': {'provider': 'ollama', 'temperature': 0.7},
            'voice': {'stt': 'vosk', 'tts': 'edge-tts'},
        }

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value) -> None:
        self.config[key] = value
