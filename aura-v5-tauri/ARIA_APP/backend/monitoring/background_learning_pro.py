"""PARTE 6: BACKGROUND LEARNING DAEMON (300 lines) — Aprendizaje optimizado.

Funciones async:
- continuous_optimization(): loop cada 3s analizando + aprendiendo
- pattern_mining(): detecta patrones recurrentes
- predictive_model(): cadena de Markov para predicciones
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


@dataclass
class LearningEvent:
    timestamp: float
    type: str = "general"
    activity: str = "unknown"
    intent: str = "general"
    mood: str = "idle"
    app: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiscoveredPattern:
    description: str = ""
    frequency: int = 0
    next_action: str = ""
    confidence: float = 0.0
    last_seen: float = 0.0
    first_seen: float = 0.0


@dataclass
class MarkovPrediction:
    action: str = ""
    probability: float = 0.0
    context: str = ""
    chain_length: int = 1


class BackgroundLearningDaemon:
    """Daemon de aprendizaje en background: optimización continua."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path.home() / ".aria" / "learning.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self._events: List[LearningEvent] = []
        self._patterns: Dict[str, List[Dict[str, Any]]] = {}
        self._markov_chain: Dict[str, Dict[str, int]] = {}
        self._running = False
        self._lock = asyncio.Lock()
        self._optimization_interval = 3.0
        self._last_optimization = 0.0
        self._session_count = 0
        self._total_events_processed = 0
        self._pattern_cache: List[DiscoveredPattern] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL, type TEXT, activity TEXT,
                intent TEXT, mood TEXT, app TEXT, metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT, frequency INTEGER,
                next_action TEXT, confidence REAL,
                last_seen REAL, first_seen REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS markov_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_state TEXT, to_state TEXT, count INTEGER
            )
        """)
        conn.commit()
        conn.close()

    async def continuous_optimization(self) -> Dict[str, Any]:
        """Optimización continua: cada 3s analiza + aprende."""
        async with self._lock:
            self._running = True
            results = {}

            try:
                capture = await self._safe_capture_screen()
                results["screen"] = capture is not None
            except Exception:
                results["screen"] = False

            try:
                pattern = await self.pattern_mining()
                results["pattern_found"] = pattern is not None and len(pattern) > 0
                if pattern:
                    self._pattern_cache = pattern
            except Exception:
                results["pattern_found"] = False

            try:
                predictions = await self.predictive_model()
                results["predictions"] = len(predictions)
            except Exception:
                results["predictions"] = 0

            try:
                events = self._events[-20:] if self._events else []
                if events:
                    self._update_markov_chain(events)
                results["markov_states"] = len(self._markov_chain)
            except Exception:
                results["markov_states"] = 0

            try:
                await self._refine_suggestions()
                results["suggestions_refined"] = True
            except Exception:
                results["suggestions_refined"] = False

            self._last_optimization = time.time()
            self._session_count += 1
            results["session"] = self._session_count
            results["total_events"] = self._total_events_processed
            results["timestamp"] = time.time()

            self._log_learning_event(
                {
                    "type": "optimization",
                    "activity": results,
                    "timestamp": time.time(),
                }
            )

            return results

    async def pattern_mining(self) -> List[DiscoveredPattern]:
        """Minería de patrones: 'SIEMPRE hace X después de Y'."""
        patterns: List[DiscoveredPattern] = []

        if len(self._events) < 5:
            return patterns

        recent = self._events[-200:]

        activity_intent: Dict[Tuple[str, str], int] = {}
        intent_mood: Dict[Tuple[str, str], int] = {}
        app_activity: Dict[Tuple[str, str], int] = []
        time_patterns: Dict[str, List[float]] = {}

        for event in recent:
            key = (event.activity, event.intent)
            activity_intent[key] = activity_intent.get(key, 0) + 1

            key2 = (event.intent, event.mood)
            intent_mood[key2] = intent_mood.get(key2, 0) + 1

            key3 = (event.app, event.activity)
            if key3 not in app_activity:
                app_activity[key3] = []
            app_activity[key3].append(event.timestamp)

            hour = time.localtime(event.timestamp).tm_hour
            hour_key = f"{event.activity}_{hour}"
            if hour_key not in time_patterns:
                time_patterns[hour_key] = []
            time_patterns[hour_key].append(event.timestamp)

        for (activity, intent), count in activity_intent.items():
            if count >= 3 and activity != "idle" and intent != "general":
                patterns.append(
                    DiscoveredPattern(
                        description=f"Actividad '{activity}' con intención '{intent}' detectada {count} veces",
                        frequency=count,
                        next_action=f"Predecir siguiente paso después de {activity}",
                        confidence=min(count / 10.0, 0.9),
                        last_seen=recent[-1].timestamp if recent else 0,
                        first_seen=recent[0].timestamp if recent else 0,
                    )
                )

        for (intent, mood), count in intent_mood.items():
            if count >= 3:
                patterns.append(
                    DiscoveredPattern(
                        description=f"Intención '{intent}' + mood '{mood}' correlacionada {count} veces",
                        frequency=count,
                        next_action=f"Ajustar respuestas para estado {mood}",
                        confidence=min(count / 10.0, 0.85),
                        last_seen=recent[-1].timestamp if recent else 0,
                        first_seen=recent[0].timestamp if recent else 0,
                    )
                )

        for (app, activity), timestamps in app_activity.items():
            if len(timestamps) >= 3:
                time_span = max(timestamps) - min(timestamps)
                if time_span > 60:
                    patterns.append(
                        DiscoveredPattern(
                            description=f"App '{app}' + actividad '{activity}' patrón recurrente",
                            frequency=len(timestamps),
                            next_action=f"Preparar herramientas para {activity}",
                            confidence=min(len(timestamps) / 15.0, 0.8),
                            last_seen=max(timestamps),
                            first_seen=min(timestamps),
                        )
                    )

        for hour_key, timestamps in time_patterns.items():
            if len(timestamps) >= 3:
                parts = hour_key.rsplit("_", 1)
                if len(parts) == 2:
                    patterns.append(
                        DiscoveredPattern(
                            description=f"Actividad '{parts[0]}' frecuente a las {parts[1]}:00",
                            frequency=len(timestamps),
                            next_action=f"Pre-activar modo {parts[0]} en hora {parts[1]}",
                            confidence=min(len(timestamps) / 10.0, 0.75),
                            last_seen=max(timestamps),
                            first_seen=min(timestamps),
                        )
                    )

        self._patterns = {p.description: p for p in patterns}
        self._log_patterns_db(patterns)
        return patterns

    async def predictive_model(self) -> List[MarkovPrediction]:
        """Modelo predictivo: cadena de Markov de acciones."""
        predictions: List[MarkovPrediction] = []

        if len(self._events) < 3:
            return self._fallback_predictions()

        recent = self._events[-50:]
        self._update_markov_chain(recent)

        if not self._markov_chain:
            return self._fallback_predictions()

        last_state = f"{recent[-1].activity}_{recent[-1].intent}" if recent else "unknown_general"

        if last_state in self._markov_chain:
            transitions = self._markov_chain[last_state]
            total = sum(transitions.values())
            if total > 0:
                sorted_next = sorted(transitions.items(), key=lambda x: x[1], reverse=True)
                for next_state, count in sorted_next[:3]:
                    prob = count / total
                    if prob > 0.05:
                        predictions.append(
                            MarkovPrediction(
                                action=next_state,
                                probability=round(prob, 3),
                                context=f"Después de '{last_state}'",
                                chain_length=1,
                            )
                        )

        if len(recent) >= 5:
            second_last = f"{recent[-2].activity}_{recent[-2].intent}" if len(recent) >= 2 else ""
            if second_last in self._markov_chain:
                transitions = self._markov_chain[second_last]
                total = sum(transitions.values())
                if total > 0:
                    sorted_next = sorted(transitions.items(), key=lambda x: x[1], reverse=True)
                    for next_state, count in sorted_next[:2]:
                        prob = count / total
                        if prob > 0.1:
                            predictions.append(
                                MarkovPrediction(
                                    action=next_state,
                                    probability=round(prob * 0.7, 3),
                                    context=f"Después de '{second_last}' (2-step)",
                                    chain_length=2,
                                )
                            )

        return predictions[:5] if predictions else self._fallback_predictions()

    def _update_markov_chain(self, events: List[LearningEvent]) -> None:
        """Actualiza cadena de Markov."""
        for i in range(len(events) - 1):
            from_state = f"{events[i].activity}_{events[i].intent}"
            to_state = f"{events[i+1].activity}_{events[i+1].intent}"

            if from_state not in self._markov_chain:
                self._markov_chain[from_state] = {}
            self._markov_chain[from_state][to_state] = (
                self._markov_chain[from_state].get(to_state, 0) + 1
            )

    def _fallback_predictions(self) -> List[MarkovPrediction]:
        return [
            MarkovPrediction(
                action="general",
                probability=0.5,
                context="Sin suficientes datos",
                chain_length=0,
            ),
            MarkovPrediction(
                action="continue_activity",
                probability=0.4,
                context="Predeterminado",
                chain_length=0,
            ),
        ]

    async def _refine_suggestions(self) -> None:
        """Refina sugerencias basadas en patrones."""
        if not self._pattern_cache:
            return

        high_confidence = [p for p in self._pattern_cache if p.confidence > 0.7]
        for pattern in high_confidence:
            self._log_learning_event(
                {
                    "type": "pattern_high_confidence",
                    "description": pattern.description,
                    "frequency": pattern.frequency,
                    "confidence": pattern.confidence,
                    "timestamp": time.time(),
                }
            )

    async def _safe_capture_screen(self) -> Optional[bool]:
        try:
            from backend.monitoring.screen_analyzer_pro import capture_screen_optimized

            result = await capture_screen_optimized()
            return result is not None
        except Exception:
            return False

    def _log_learning_event(self, data: Dict[str, Any]) -> None:
        self._total_events_processed += 1
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO learning_events (timestamp, type, activity, intent, mood, app, metadata) VALUES (?,?,?,?,?,?,?)",
                (
                    data.get("timestamp", time.time()),
                    data.get("type", "general"),
                    data.get("activity", "unknown"),
                    data.get("intent", "general"),
                    data.get("mood", "idle"),
                    data.get("app", "unknown"),
                    json.dumps(data.get("metadata", {})),
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _log_patterns_db(self, patterns: List[DiscoveredPattern]) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            for p in patterns:
                conn.execute(
                    "INSERT OR REPLACE INTO discovered_patterns (description, frequency, next_action, confidence, last_seen, first_seen) VALUES (?,?,?,?,?,?)",
                    (
                        p.description,
                        p.frequency,
                        p.next_action,
                        p.confidence,
                        p.last_seen,
                        p.first_seen,
                    ),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def record_event(self, data: Dict[str, Any]) -> None:
        """Registra evento para aprendizaje."""
        event = LearningEvent(
            timestamp=data.get("timestamp", time.time()),
            type=data.get("type", "general"),
            activity=data.get("activity", "unknown"),
            intent=data.get("intent", "general"),
            mood=data.get("mood", "idle"),
            app=data.get("app", "unknown"),
            metadata=data.get("metadata", {}),
        )
        self._events.append(event)
        if len(self._events) > 5000:
            self._events = self._events[-3000:]
        self._log_learning_event(data)
