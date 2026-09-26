"""
AURA Deep Learning Module
Autoaprendizaje autónomo para mejorar habilidades y conocimientos.
"""

from __future__ import annotations

import os
import time
import json
import hashlib
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from pathlib import Path


AURA_BACKEND_URL = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
AURA_API_KEY = os.getenv("AURA_API_KEY", "")
LEARNING_DIR = Path(__file__).resolve().parent.parent / "learning_data"
LEARNING_DIR.mkdir(exist_ok=True)


class DeepLearningModule:
    def __init__(self, backend_url: str = AURA_BACKEND_URL, api_key: str = AURA_API_KEY) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.knowledge_base: List[Dict[str, Any]] = []
        self.load_state()

    def load_state(self) -> None:
        state_file = LEARNING_DIR / "deep_learning_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.skills = data.get("skills", {})
                self.knowledge_base = data.get("knowledge_base", [])
            except Exception:
                pass

    def save_state(self) -> None:
        state_file = LEARNING_DIR / "deep_learning_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "skills": self.skills,
                    "knowledge_base": self.knowledge_base,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def learn_from_interaction(self, prompt: str, response: str, provider: str, feedback: Optional[str] = None) -> None:
        skill_id = hashlib.sha256(f"{prompt}:{provider}".encode("utf-8")).hexdigest()[:16]
        if skill_id not in self.skills:
            self.skills[skill_id] = {
                "prompt_pattern": prompt[:100],
                "provider": provider,
                "uses": 0,
                "success_rate": 0.0,
                "last_used": time.time(),
            }
        skill = self.skills[skill_id]
        skill["uses"] += 1
        skill["last_used"] = time.time()
        if feedback == "up":
            skill["success_rate"] = min(1.0, skill["success_rate"] + 0.1)
        elif feedback == "down":
            skill["success_rate"] = max(0.0, skill["success_rate"] - 0.1)
        self.save_state()

    def learn_from_internet(self, topic: str) -> Optional[Dict[str, Any]]:
        prompt = (
            f"Investigá sobre: {topic}. "
            "Devuelve SOLO un JSON con: "
            '{"summary": "...", "key_facts": ["...", "..."], "sources": ["..."], "confidence": 0.0}. '
            "Sé conciso y factual."
        )
        payload = {"prompt": prompt, "session_id": "deep-learning", "user_id": "system"}
        result = self._post("/api/chat", payload)
        if result and result.get("text"):
            try:
                data = json.loads(result["text"])
                entry = {
                    "topic": topic,
                    "summary": data.get("summary", ""),
                    "key_facts": data.get("key_facts", []),
                    "sources": data.get("sources", []),
                    "confidence": data.get("confidence", 0.0),
                    "timestamp": time.time(),
                }
                self.knowledge_base.append(entry)
                self.save_state()
                return entry
            except Exception:
                pass
        return None

    def query_knowledge(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results = []
        query_lower = query.lower()
        for entry in self.knowledge_base:
            score = 0.0
            if query_lower in entry.get("topic", "").lower():
                score += 0.5
            for fact in entry.get("key_facts", []):
                if query_lower in fact.lower():
                    score += 0.3
            if score > 0:
                results.append({**entry, "relevance": score})
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        return results[:max_results]

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.backend_url}{endpoint}",
            data=data,
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as exc:
            print(f"[DeepLearning] Error en {endpoint}: {exc}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self.skills),
            "total_knowledge": len(self.knowledge_base),
            "top_skills": sorted(self.skills.values(), key=lambda x: x.get("uses", 0), reverse=True)[:5],
        }
