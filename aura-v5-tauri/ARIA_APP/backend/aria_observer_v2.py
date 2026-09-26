"""ARIA Observer v2 — Enhanced monitoring with intent detection, keywords, suggestions, mood tracking."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ARIA_APP.frontend.aria_observer import AriaObserver

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import win32gui

    try:
        import win32process
    except ImportError:
        win32process = None
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


INTENT_KEYWORDS: Dict[str, List[str]] = {
    "design": [
        "imagen",
        "image",
        "edit",
        "diseño",
        "drawing",
        "paint",
        "figma",
        "canva",
        "photoshop",
        "brush",
        "color",
    ],
    "storytelling": [
        "anime",
        "story",
        "narración",
        "reading",
        "read",
        "libro",
        "novel",
        "fanfic",
        "comic",
        "manga",
    ],
    "creation": [
        "code",
        "coding",
        "escribir",
        "programar",
        "editor",
        "dev",
        "vscode",
        "pycharm",
        "terminal",
        "script",
    ],
    "research": [
        "search",
        "buscar",
        "investigar",
        "research",
        "google",
        "wikipedia",
        "article",
        "paper",
    ],
    "communication": ["chat", "message", "correo", "email", "discord", "slack", "talk", "call"],
    "media": ["video", "music", "stream", "youtube", "spotify", "movie", "audio", "podcast"],
    "security": [
        "security",
        "password",
        "firewall",
        "network",
        "cyber",
        "encryption",
        "ssl",
        "vpn",
        "threat",
    ],
}

CONTENT_MAP: Dict[str, str] = {
    "design": "character",
    "storytelling": "story",
    "creation": "world",
    "research": "prompt",
    "security": "prompt",
    "media": "prompt",
    "communication": "story",
}

MOOD_PATTERNS: Dict[str, List[str]] = {
    "explorando": ["browsing", "search", "google", "wikipedia", "slow"],
    "creando": ["coding", "editor", "writing", "drawing", "intense"],
    "relajado": ["streaming", "music", "video", "youtube", "idle"],
}


class AriaObserverV2(AriaObserver):
    """Enhanced AriaObserver with AI-driven intent and mood analysis."""

    def __init__(self, backend_url: str = "http://localhost:8000", poll_interval: int = 2):
        super().__init__(backend_url=backend_url, poll_interval=poll_interval)
        self._intent_history: List[Dict[str, Any]] = []
        self._mood_history: List[Dict[str, Any]] = []
        self._keyword_history: List[str] = []
        self._suggestion_log: List[Dict[str, Any]] = []
        self._suggestion_db = str(Path.home() / ".aria" / "suggestions.db")
        self._init_suggestion_db()
        self._activity_speed = 0.0
        self._search_count = 0
        self._modification_count = 0
        self._mood = "idle"
        self._mood_intensity = 0

    def _init_suggestion_db(self) -> None:
        Path(os.path.dirname(self._suggestion_db)).mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._suggestion_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suggestion_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                suggestion_id TEXT,
                suggestion_type TEXT,
                title TEXT,
                context TEXT,
                status TEXT DEFAULT 'pending',
                feedback TEXT DEFAULT ''
            )
        """)
        conn.commit()
        conn.close()

    def _log_suggestion(
        self, suggestion_id: str, suggestion_type: str, title: str, context: str
    ) -> None:
        conn = sqlite3.connect(self._suggestion_db)
        conn.execute(
            "INSERT INTO suggestion_log (timestamp, suggestion_id, suggestion_type, title, context) VALUES (?, ?, ?, ?, ?)",
            (time.time(), suggestion_id, suggestion_type, title, context),
        )
        conn.commit()
        conn.close()

    async def detect_intent(self) -> Dict[str, Any]:
        context = self.build_context()
        app = (context.get("current_app") or "").lower()
        title = (context.get("window_title") or "").lower()
        searches = context.get("searches", [])
        queries = " ".join(s.get("query", "").lower() for s in searches)
        files = context.get("open_files", [])
        file_names = " ".join(f.get("file_path", "").lower() for f in files)
        combined = f"{app} {title} {queries} {file_names}"
        scores: Dict[str, float] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                if kw in combined:
                    score += 1.0
            if score > 0:
                scores[intent] = score

        if not scores:
            return {"intent": "general", "confidence": 0.1, "category": "neutral"}

        best_intent = max(scores, key=scores.get)
        max_score = scores[best_intent]
        confidence = min(max_score / 3.0, 1.0)
        category = CONTENT_MAP.get(best_intent, "general")

        result = {"intent": best_intent, "confidence": round(confidence, 2), "category": category}
        self._intent_history.append({**result, "timestamp": time.time()})
        return result

    async def extract_context_keywords(self) -> List[str]:
        context = self.build_context()
        keywords: List[str] = []

        for s in context.get("searches", []):
            query = s.get("query", "")
            for word in re.findall(r"\b\w{3,}\b", query.lower()):
                if word not in keywords and len(word) >= 3:
                    keywords.append(word)

        for f in context.get("open_files", []):
            path = f.get("file_path", "")
            name = Path(path).stem.lower()
            for word in re.findall(r"[a-z]{3,}", name):
                if word not in keywords and len(word) >= 3:
                    keywords.append(word)

        for intent, kws in INTENT_KEYWORDS.items():
            for kw in kws:
                if kw in " ".join(keywords) and kw not in keywords:
                    keywords.append(kw)

        keywords = keywords[:20]
        self._keyword_history = keywords
        return keywords

    async def suggest_based_on_context(self) -> Dict[str, Any]:
        intent = await self.detect_intent()
        keywords = await self.extract_context_keywords()

        intent_type = intent.get("intent", "general")
        category = intent.get("category", "general")
        confidence = intent.get("confidence", 0.0)

        suggestion_type = category
        reason_parts = []
        if keywords:
            reason_parts.append(f"Palabras clave: {', '.join(keywords[:5])}")
        if intent_type != "general":
            reason_parts.append(f"Intención detectada: {intent_type}")
        reason = "; ".join(reason_parts) if reason_parts else "Actividad general"

        endpoint_map = {
            "story": "/api/aria/generate/story",
            "character": "/api/aria/generate/character",
            "world": "/api/aria/generate/world",
            "prompt": "/api/aria/generate/prompt",
            "general": "/api/aria/content/suggest",
        }

        suggestion_id = f"sig_{int(time.time())}"
        result = {
            "suggestion_type": suggestion_type,
            "reason": reason,
            "endpoint": endpoint_map.get(suggestion_type, "/api/aria/content/suggest"),
            "keywords": keywords[:5],
            "intent": intent,
            "confidence": confidence,
        }
        self._log_suggestion(suggestion_id, suggestion_type, reason, json.dumps(result))
        return {**result, "suggestion_id": suggestion_id}

    async def track_mood(self) -> Dict[str, Any]:
        context = self.build_context()
        app = (context.get("current_app") or "").lower()
        title = (context.get("window_title") or "").lower()
        searches = context.get("searches", [])
        activity = context.get("activity", "unknown")

        search_count = len(searches)
        if hasattr(self, "_search_count"):
            self._search_count = search_count

        open_files = context.get("open_files", [])
        mod_count = 0
        for f in open_files:
            path = f.get("file_path", "")
            if any(ext in path.lower() for ext in [".py", ".js", ".ts", ".md", ".txt", ".doc"]):
                mod_count += 1
        self._modification_count = mod_count

        if search_count > 5 or "browser" in app or "search" in app:
            if "explore" in app or "search" in app or "google" in app:
                mood = "explorando"
                intensity = min(search_count * 10, 80)
            else:
                mood = "explorando"
                intensity = min(search_count * 8, 60)
        elif mod_count > 2 or "editor" in app or "code" in app or "vscode" in app:
            mood = "creando"
            intensity = min(mod_count * 15 + 20, 100)
        elif "stream" in app or "video" in app or "music" in app or "youtube" in app:
            mood = "relajado"
            intensity = 30
        elif activity == "idle" or not app or app == "unknown":
            mood = "relajado"
            intensity = 10
        else:
            mood = "creando"
            intensity = 50

        self._mood = mood
        self._mood_intensity = intensity
        mood_result = {"mood": mood, "intensity": intensity}
        self._mood_history.append({**mood_result, "timestamp": time.time()})
        return mood_result
