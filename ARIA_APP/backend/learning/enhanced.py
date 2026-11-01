import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class EnhancedLearning:
    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            base = Path(__file__).resolve().parent.parent
            storage_dir = str(base / "logs" / "learning_enhanced")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.storage_dir / "state.json"
        self.state: Dict[str, Any] = {"patterns": {}, "successes": {}, "confidence": {}}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, pattern: str, ok: bool, context: str = "") -> Dict[str, Any]:
        bucket = "successes" if ok else "patterns"
        item = self.state[bucket].setdefault(pattern, {"count": 0, "context": "", "last_seen": 0.0})
        item["count"] += 1
        item["last_seen"] = time.time()
        if context:
            item["context"] = context
        conf = self.state["confidence"].setdefault(pattern, 0.5)
        conf = min(0.99, conf + (0.08 if ok else -0.12))
        self.state["confidence"][pattern] = max(0.01, conf)
        self._save()
        return {"pattern": pattern, "ok": ok, "confidence": round(conf, 3)}

    def consolidate(self) -> Dict[str, Any]:
        promoted = []
        for pattern, item in self.state["patterns"].items():
            if item["count"] >= 3:
                promoted.append({"pattern": pattern, "rule": item.get("context") or f"Evitar: {pattern}"})
        return {"promoted": promoted, "count": len(promoted)}

    def summary(self) -> Dict[str, Any]:
        return {
            "errors": len(self.state["patterns"]),
            "successes": len(self.state["successes"]),
            "avg_confidence": round(sum(self.state["confidence"].values()) / max(1, len(self.state["confidence"])), 3),
        }
