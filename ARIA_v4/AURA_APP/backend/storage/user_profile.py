"""User Profile — Perfil de usuario con aprendizaje"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict


class UserProfile:
    """Perfil de usuario persistente"""

    def __init__(self):
        self.profile_file = Path('ARIA_v4/AURA_APP/data/user_profile.json')
        self.profile = self._load()

    def _load(self) -> Dict:
        if self.profile_file.exists():
            with open(self.profile_file) as f:
                return json.load(f)
        return {
            'name': 'Usuario',
            'language': 'es',
            'timezone': 'America/Lima',
            'preferences': {},
            'behavior_patterns': [],
            'favorite_commands': [],
            'learning_style': 'visual',
            'created': datetime.now().isoformat(),
        }

    def save(self) -> None:
        with open(self.profile_file, 'w') as f:
            json.dump(self.profile, f, indent=2)

    def update(self, updates: Dict) -> None:
        self.profile.update(updates)
        self.save()

    def get(self, key: str, default=None):
        return self.profile.get(key, default)

    def get_all(self) -> Dict:
        return self.profile
