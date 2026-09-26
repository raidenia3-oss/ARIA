"""Cache Manager — Gestiona cache USB y sistema"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class CacheManager:
    """Gestiona cache de USB y sistema"""

    def __init__(self):
        self.cache_dir = Path('ARIA_v4/AURA_APP/data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / 'index.json'
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        if self.index_file.exists():
            with open(self.index_file) as f:
                return json.load(f)
        return {'files': {}, 'last_cleanup': None}

    def _save_index(self) -> None:
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)

    def cache_file(self, source_path: str, tag: str = 'default') -> str:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source_path)
        cache_path = self.cache_dir / tag / source.name
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, cache_path)
        self.index['files'][str(source)] = {
            'cached_at': datetime.now().isoformat(),
            'tag': tag,
            'cache_path': str(cache_path),
            'size': source.stat().st_size,
        }
        self._save_index()
        return str(cache_path)

    def get_cached(self, source_path: str) -> str:
        entry = self.index['files'].get(source_path)
        return entry['cache_path'] if entry else None

    def clear(self) -> int:
        count = 0
        for file in self.cache_dir.rglob('*'):
            if file.is_file():
                file.unlink()
                count += 1
        self.index = {'files': {}, 'last_cleanup': datetime.now().isoformat()}
        self._save_index()
        return count

    def get_stats(self) -> Dict:
        total_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
        return {
            'total_files': len(self.index['files']),
            'total_size_mb': total_size / (1024**2),
            'cache_dir': str(self.cache_dir),
            'last_cleanup': self.index.get('last_cleanup'),
        }
