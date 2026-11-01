# Universal IO: read photos/videos/docs, fail-closed
from __future__ import annotations
import os
from typing import Any, Dict, List


class UniversalIO:
    def __init__(self) -> None:
        self.exts = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff', '.webp'],
            'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
            'doc': ['.pdf', '.txt', '.md', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.json', '.html'],
        }

    def list(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        if not path or not os.path.exists(path):
            return {"status": "invalid", "files": []}
        files: List[str] = []
        if recursive:
            for root, _, fs in os.walk(path):
                for f in fs:
                    files.append(os.path.join(root, f))
        else:
            for f in os.listdir(path):
                p = os.path.join(path, f)
                if os.path.isfile(p):
                    files.append(p)
        return {"status": "ok", "files": files, "count": len(files)}

    def classify(self, path: str) -> Dict[str, Any]:
        ext = os.path.splitext(path)[1].lower()
        for k, v in self.exts.items():
            if ext in v:
                return {"path": path, "type": k}
        return {"path": path, "type": "other"}


universal_io = UniversalIO()
