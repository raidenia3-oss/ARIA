"""PARTE 5: BACKGROUND LEARNING DAEMON (250 lines) — Aprendizaje continuo.

Clase: BackgroundLearningDaemon
- Continuous learning loop (5s interval)
- Pattern detection
- Suggestion optimization
- Privacy preserving

Storage: SQLite BehaviorPattern
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from backend.monitoring.screen_analyzer import ScreenAnalyzer

    HAS_SCREEN = True
except ImportError:
    HAS_SCREEN = False

try:
    from backend.monitoring.audio_analyzer import AudioAnalyzer

    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    from backend.aria_observer_v2 import AriaObserverV2

    HAS_OBSERVER = True
except ImportError:
    HAS_OBSERVER = False

try:
    from backend.aria_integration import AriaIntegration

    HAS_G7 = True
except ImportError:
    HAS_G7 = False


@dataclass
class BehaviorPattern:
    pattern_id: str
    description: str
    frequency: int = 0
    confidence: float = 0.0
    last_triggered: float = 0.0
    next_suggestion: str = ""


class BackgroundLearningDaemon:
    """Aprendizaje en background continuo."""

    PRIVACY_SENSITIVE_PATTERNS = [
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
        r"(?i)(password|passwd|contraseña)[\s=:]+[^\s]+",
    ]

    PATTERN_TEMPLATES = [
        (
            "designs character after anime",
            "storytelling",
            "character",
            "Generate a character based on anime style",
        ),
        (
            "generates stories with ambient music",
            "media",
            "story",
            "Start a new story while music plays",
        ),
        (
            "searches worldbuilding after coding",
            "creation",
            "world",
            "Build a fantasy world for your project",
        ),
        (
            "reads manga after work hours",
            "storytelling",
            "story",
            "Continue reading your manga series",
        ),
        (
            "codes more after afternoon tea",
            "creation",
            "creation",
            "Open your IDE and continue coding",
        ),
    ]

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(os.path.expanduser("~/.aria/behavior_patterns.db"))
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop_task: Optional[asyncio.Task] = None
        self._screen_analyzer: Optional[Any] = None
        self._audio_analyzer: Optional[Any] = None
        self._observer: Optional[Any] = None
        self._integration: Optional[Any] = None
        self._learning_data: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        if HAS_SCREEN:
            try:
                self._screen_analyzer = ScreenAnalyzer()
            except Exception:
                pass
        if HAS_AUDIO:
            try:
                self._audio_analyzer = AudioAnalyzer()
            except Exception:
                pass
        if HAS_OBSERVER:
            try:
                self._observer = AriaObserverV2()
            except Exception:
                pass
        if HAS_G7:
            try:
                self._integration = AriaIntegration()
            except Exception:
                pass

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS behavior_patterns (
                pattern_id TEXT PRIMARY KEY,
                description TEXT,
                frequency INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                last_triggered REAL DEFAULT 0,
                next_suggestion TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                event_type TEXT,
                data TEXT,
                privacy_filtered BOOLEAN DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    async def continuous_learning_loop(self) -> None:
        """Loop de aprendizaje continuo cada 5 segundos."""
        while self._running:
            try:
                await self._learning_step()
            except Exception:
                pass
            await asyncio.sleep(5)

    async def _learning_step(self) -> None:
        """Un paso de aprendizaje."""
        screen_data = {}
        audio_data = {}

        if self._screen_analyzer:
            try:
                capture = await self._screen_analyzer.capture_screen()
                screen_data = {
                    "active_app": capture.active_app,
                    "semantic_context": capture.semantic_context,
                    "confidence": capture.confidence,
                }
            except Exception:
                pass

        if self._audio_analyzer:
            try:
                activity = await self._audio_analyzer.detect_audio_activity()
                audio_data = {
                    "audio_detected": activity.get("audio_detected"),
                    "volume": activity.get("volume"),
                }
            except Exception:
                pass

        event = {
            "timestamp": time.time(),
            "screen": screen_data,
            "audio": audio_data,
            "observer": self._get_observer_data(),
        }

        self._lock.acquire()
        self._learning_data.append(event)
        if len(self._learning_data) > 1000:
            self._learning_data = self._learning_data[-1000:]
        self._lock.release()

        await self._pattern_detection()
        self._log_learning(event)

    def _get_observer_data(self) -> dict:
        if self._observer:
            try:
                intent = asyncio.run(self._observer.detect_intent())
                mood = asyncio.run(self._observer.track_mood())
                return {"intent": intent, "mood": mood}
            except Exception:
                return {}
        return {}

    async def _pattern_detection(self) -> None:
        """Detecta patrones de comportamiento."""
        if len(self._learning_data) < 10:
            return

        recent = self._learning_data[-50:]
        intent_counts: Dict[str, int] = {}
        app_counts: Dict[str, int] = {}
        mood_counts: Dict[str, int] = {}

        for entry in recent:
            observer = entry.get("observer", {})
            intent = (
                observer.get("intent", {}).get("intent", "general")
                if isinstance(observer.get("intent"), dict)
                else "general"
            )
            mood = (
                observer.get("mood", {}).get("mood", "idle")
                if isinstance(observer.get("mood"), dict)
                else "idle"
            )
            app = entry.get("screen", {}).get("active_app", "unknown")

            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            app_counts[app] = app_counts.get(app, 0) + 1
            mood_counts[mood] = mood_counts.get(mood, 0) + 1

        for pattern_id, desc, related_intent, suggestion in self.PATTERN_TEMPLATES:
            if related_intent in intent_counts:
                freq = intent_counts[related_intent]
                if freq >= 3:
                    confidence = min(freq / 10.0, 1.0)
                    self._save_pattern(pattern_id, desc, freq, confidence, suggestion)

    def _save_pattern(self, pid, desc, freq, confidence, suggestion) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO behavior_patterns (pattern_id, description, frequency, confidence, last_triggered, next_suggestion) VALUES (?,?,?,?,?,?)",
            (pid, desc, freq, confidence, time.time(), suggestion),
        )
        conn.commit()
        conn.close()

    def _log_learning(self, event: dict) -> None:
        conn = sqlite3.connect(self.db_path)
        filtered = self._filter_privacy(event)
        conn.execute(
            "INSERT INTO learning_log (timestamp, event_type, data, privacy_filtered) VALUES (?,?,?,?)",
            (time.time(), "learning_step", json.dumps(filtered)[:500], not filtered == event),
        )
        conn.commit()
        conn.close()

    async def optimize_suggestions(self) -> List[Dict[str, Any]]:
        """Optimiza sugerencias basadas en patrones."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM behavior_patterns WHERE frequency >= 2 ORDER BY confidence DESC LIMIT 5"
        ).fetchall()
        conn.close()

        suggestions = []
        for row in rows:
            pattern_id, desc, freq, conf, last_trig, next_sug = row
            suggestions.append(
                {
                    "pattern_id": pattern_id,
                    "description": desc,
                    "frequency": freq,
                    "confidence": conf,
                    "suggestion": next_sug,
                }
            )
        return suggestions

    def _filter_privacy(self, data: dict) -> dict:
        filtered = json.loads(json.dumps(data))
        for section in ["screen", "audio", "observer"]:
            if section in filtered and isinstance(filtered[section], dict):
                text = json.dumps(filtered[section])
                for pattern in self.PRIVACY_SENSITIVE_PATTERNS:
                    text = re.sub(pattern, "[REDACTED]", text)
                filtered[section] = json.loads(text) if text else {}
        return filtered

    @property
    def privacy_score(self) -> float:
        try:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM learning_log").fetchone()[0]
            filtered = conn.execute(
                "SELECT COUNT(*) FROM learning_log WHERE privacy_filtered = 1"
            ).fetchone()[0]
            conn.close()
            if total == 0:
                return 100.0
            return (filtered / total) * 100
        except Exception:
            return 100.0

    async def start(self) -> None:
        self._running = True
        self._loop_task = asyncio.create_task(self.continuous_learning_loop())

    async def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

    def get_patterns(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM behavior_patterns ORDER BY frequency DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return [
            {
                "pattern_id": r[0],
                "description": r[1],
                "frequency": r[2],
                "confidence": r[3],
                "next_suggestion": r[5],
            }
            for r in rows
        ]
