"""Skill Storage — Persistencia de skills"""

import json
from pathlib import Path
from typing import Dict, List


class SkillStorage:
    """Almacena y recupera skills"""

    def __init__(self):
        self.skills_file = Path('ARIA_v4/AURA_APP/data/skills_registry.json')
        self.skills: Dict = self._load()

    def _load(self) -> Dict:
        if self.skills_file.exists():
            with open(self.skills_file) as f:
                return json.load(f)
        return {'skills': {}, 'categories': {}}

    def save(self) -> None:
        with open(self.skills_file, 'w') as f:
            json.dump(self.skills, f, indent=2)

    def register(self, name: str, definition: str, category: str = 'general') -> None:
        self.skills['skills'][name] = {
            'definition': definition,
            'category': category,
            'created': str(Path(__file__).stat().st_mtime),
        }
        if category not in self.skills['categories']:
            self.skills['categories'][category] = []
        self.skills['categories'][category].append(name)
        self.save()

    def get(self, name: str) -> Dict:
        return self.skills['skills'].get(name, {})

    def list_all(self) -> List[str]:
        return list(self.skills['skills'].keys())

    def list_by_category(self, category: str) -> List[str]:
        return self.skills['categories'].get(category, [])
