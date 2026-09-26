"""Config — Configuración central"""

import json
from pathlib import Path
from typing import Dict


class Config:
    """Configuración central de ARIA"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(Path('ARIA_v4/AURA_APP/backend/config/config.json'))
        self.config = self._load()

    def _load(self) -> Dict:
        if Path(self.config_path).exists():
            with open(self.config_path) as f:
                return json.load(f)
        return self._defaults()

    def _defaults(self) -> Dict:
        return {
            'app': {
                'name': 'ARIA OS',
                'version': '4.0.0',
                'mode': 'standalone',
            },
            'ai': {
                'provider': 'ollama',
                'model': 'dolphin-2_6-phi-2',
                'temperature': 0.7,
                'max_tokens': 2048,
            },
            'voice': {
                'stt': 'vosk',
                'tts': 'edge-tts',
                'language': 'es',
            },
            'storage': {
                'db_path': 'ARIA_v4/AURA_APP/data/cerebro.db',
                'memory_limit_mb': 100,
            },
            'ui': {
                'theme': 'dark',
                'language': 'es',
            },
        }

    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            value = value.get(k, default) if isinstance(value, dict) else default
        return value

    def set(self, key: str, value) -> None:
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save()

    def _save(self) -> None:
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
