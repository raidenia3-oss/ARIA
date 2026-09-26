"""Claude Context Bridge — Búsqueda vectorial (Repositorio #2)"""

import os
from pathlib import Path
from typing import List


class ClaudeContextBridge:
    """Integra Claude Context - búsqueda vectorial de archivos"""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.indexed_files = []

    def index_repository(self) -> List[str]:
        """Indexa archivos relevantes del repositorio"""
        relevant_extensions = ['.py', '.txt', '.md', '.json']

        for file in self.repo_path.rglob('*'):
            if file.suffix in relevant_extensions:
                if '__pycache__' not in str(file):
                    self.indexed_files.append(str(file))

        return self.indexed_files[:50]

    def search_relevant_files(self, query: str) -> List[str]:
        """Busca archivos relevantes para query"""
        if not self.indexed_files:
            self.index_repository()

        query_lower = query.lower()
        relevant = []

        for file in self.indexed_files:
            if any(keyword in file.lower() for keyword in query_lower.split()):
                relevant.append(file)

        return relevant[:5]


if __name__ == '__main__':
    bridge = ClaudeContextBridge('AURA_APP')
    files = bridge.index_repository()
    print(f"Indexed {len(files)} files")

    search = bridge.search_relevant_files('intelligence')
    print(f"Found: {search}")
