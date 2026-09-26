"""Cache — Indexing y cache del sistema"""

import json
from pathlib import Path
from typing import Dict, Optional


class Cache:
    """Sistema de cache e indexing"""

    def __init__(self):
        self.cache_dir = Path('ARIA_v4/AURA_APP/data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / 'search_index.json'
        self.index = self._load()

    def _load(self) -> Dict:
        if self.index_file.exists():
            with open(self.index_file) as f:
                return json.load(f)
        return {'index': {}, 'last_update': None}

    def _save(self) -> None:
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def index_file(self, path: str, content: str) -> None:
        self.index['index'][path] = {
            'content_preview': content[:200],
            'length': len(content),
        }
        self.index['last_update'] = str(Path(path).stat().st_mtime) if Path(path).exists() else None
        self._save()

    def search(self, query: str) -> List[str]:
        results = []
        query_lower = query.lower()
        for path, data in self.index['index'].items():
            if query_lower in data.get('content_preview', '').lower():
                results.append(path)
        return results[:10]

    def clear(self) -> None:
        self.index = {'index': {}, 'last_update': None}
        self._save()
