"""USB Model Loader — Carga .gguf desde USB"""

from pathlib import Path
from typing import Dict, List


class ModelLoader:
    """Carga modelos desde USB/cache"""

    def __init__(self):
        self.loaded_models = {}
        self.model_dir = Path('ARIA_v4/AURA_APP/data/models')
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def discover_models(self, search_paths: List[str] = None) -> List[Dict]:
        models = []
        paths = search_paths or [str(self.model_dir)]
        for path_str in paths:
            path = Path(path_str)
            if not path.exists():
                continue
            for model_file in path.rglob('*.gguf'):
                models.append({
                    'path': str(model_file),
                    'name': model_file.stem,
                    'size_mb': model_file.stat().st_size / (1024**2),
                    'format': 'GGUF',
                })
            for model_file in path.rglob('*.bin'):
                models.append({
                    'path': str(model_file),
                    'name': model_file.stem,
                    'size_mb': model_file.stat().st_size / (1024**2),
                    'format': 'BIN',
                })
        return models

    def load_model(self, model_path: str) -> Dict:
        if model_path in self.loaded_models:
            return self.loaded_models[model_path]
        model = {
            'path': model_path,
            'loaded': True,
            'timestamp': str(Path(model_path).stat().st_mtime),
        }
        self.loaded_models[model_path] = model
        return model

    def unload_model(self, model_path: str) -> bool:
        if model_path in self.loaded_models:
            del self.loaded_models[model_path]
            return True
        return False

    def list_loaded(self) -> List[Dict]:
        return list(self.loaded_models.values())
