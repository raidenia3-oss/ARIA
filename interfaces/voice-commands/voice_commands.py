from __future__ import annotations

from typing import Dict


class VoiceCommandRouter:
    def __init__(self, command_map: Dict[str, str] | None = None) -> None:
        self.command_map = command_map or {
            'ejecutar training': 'run_training',
            'detener servicios': 'stop_services',
            'publicar estado': 'publish_status',
            'reiniciar bot': 'restart_bot',
        }

    def route(self, text: str) -> str:
        return self.command_map.get(text.lower().strip(), 'unknown')
