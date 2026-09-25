"""PARTE 4: CONTEXTUAL UNDERSTANDING ENGINE (350 lines) — Comprensión contextual.

Clase: ContextualUnderstandingEngine
- Synthesizes screen + audio + observer
- understand_current_state() → contexto completo
- predict_next_action() → predicción
- generate_contextual_response() → respuesta proactiva
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
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
class ContextState:
    state: str = "unknown"
    confidence: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    intent: str = "general"
    mood: str = "idle"
    activity: str = "unknown"
    active_app: str = "unknown"
    suggestions: List[str] = field(default_factory=list)
    next_action: str = ""
    next_action_confidence: float = 0.0


class ContextualUnderstandingEngine:
    """Sintetiza screen + audio + observer en contexto comprensible."""

    INTENT_MAP = {
        "design": ["character", "image", "draw", "anime", "art", "figma"],
        "storytelling": ["anime", "story", "read", "book", "tensura", "fantasy", "narración"],
        "creation": ["code", "program", "editor", "dev", "vscode", "terminal"],
        "research": ["search", "google", "wikipedia", "article", "research"],
        "communication": ["chat", "email", "discord", "message", "call", "slack"],
        "media": ["video", "music", "stream", "youtube", "movie", "audio"],
        "security": ["security", "password", "network", "cyber", "encryption"],
    }

    def __init__(self):
        self.screen_analyzer: Optional[Any] = None
        self.audio_analyzer: Optional[Any] = None
        self.observer: Optional[Any] = None
        self.integration: Optional[Any] = None

        if HAS_SCREEN:
            try:
                self.screen_analyzer = ScreenAnalyzer()
            except Exception:
                pass
        if HAS_AUDIO:
            try:
                self.audio_analyzer = AudioAnalyzer()
            except Exception:
                pass
        if HAS_OBSERVER:
            try:
                self.observer = AriaObserverV2()
            except Exception:
                pass
        if HAS_G7:
            try:
                self.integration = AriaIntegration()
            except Exception:
                pass

        self._behavior_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def understand_current_state(self) -> ContextState:
        """Combina screen, audio, observer → estado completo."""
        screen_data = {}
        audio_data = {}
        observer_data = {}

        if self.screen_analyzer:
            try:
                capture = await self.screen_analyzer.capture_screen()
                screen_data = {
                    "active_app": capture.active_app,
                    "ocr_text": capture.ocr_text[:500],
                    "semantic_context": capture.semantic_context,
                    "changed": capture.changed,
                }
            except Exception:
                pass

        if self.audio_analyzer:
            try:
                activity = await self.audio_analyzer.detect_audio_activity()
                ambient = await self.audio_analyzer.ambient_sound_analysis()
                speech = await self.audio_analyzer.speech_recognition()
                audio_data = {
                    "audio_detected": activity.get("audio_detected"),
                    "volume": activity.get("volume"),
                    "ambient_type": ambient.get("ambient_type"),
                    "quietness": ambient.get("quietness_score"),
                    "speech": speech,
                }
            except Exception:
                pass

        if self.observer:
            try:
                context = self.observer.build_context()
                intent = await self.observer.detect_intent()
                mood = await self.observer.track_mood()
                observer_data = {
                    "context": context,
                    "intent": intent,
                    "mood": mood,
                }
            except Exception:
                pass

        active_app = screen_data.get("active_app") or observer_data.get("context", {}).get(
            "current_app", "unknown"
        )
        intent = observer_data.get("intent", {}).get("intent", "general")
        mood = observer_data.get("mood", {}).get("mood", "idle")

        semantic_understanding = screen_data.get("semantic_context", f"Using {active_app}")

        all_suggestions = self._generate_all_suggestions(
            intent, mood, active_app, screen_data, audio_data
        )

        confidence = self._calc_confidence(screen_data, audio_data, observer_data)

        state = ContextState(
            state=semantic_understanding,
            confidence=confidence,
            details={
                "screen": screen_data,
                "audio": audio_data,
                "observer": observer_data,
            },
            intent=intent,
            mood=mood,
            activity=screen_data.get("semantic_context", "unknown"),
            active_app=active_app,
            suggestions=all_suggestions,
        )

        self._behavior_history.append(
            {
                "timestamp": time.time(),
                "state": state.state,
                "intent": intent,
                "mood": mood,
                "app": active_app,
            }
        )
        if len(self._behavior_history) > 500:
            self._behavior_history = self._behavior_history[-500:]

        return state

    def _generate_all_suggestions(self, intent, mood, app, screen, audio) -> List[str]:
        suggestions = []
        if intent in ("storytelling", "design"):
            suggestions.append(f"Story Mode: Generate content about {intent}")
        if intent in ("creation",):
            suggestions.append("Create Mode: Start a new project")
        if mood == "exploring":
            suggestions.append("Explore: Search for new topics")
        if mood == "relaxed":
            suggestions.append("Relax: Ambient music suggestion")
        if audio.get("music_playing"):
            suggestions.append("Music: Continue listening")
        return suggestions

    def _calc_confidence(self, screen, audio, observer) -> float:
        score = 0.1
        if screen.get("active_app") and screen["active_app"] != "unknown":
            score += 0.25
        if observer.get("intent") and observer["intent"].get("intent") != "general":
            score += 0.25
        if observer.get("mood") and observer["mood"].get("mood") != "idle":
            score += 0.15
        if audio.get("audio_detected") is not None:
            score += 0.15
        if screen.get("semantic_context") and screen["semantic_context"] != "unknown":
            score += 0.25
        return min(score, 1.0)

    async def predict_next_action(self) -> Dict[str, Any]:
        """Predice próxima acción basada en historial."""
        if len(self._behavior_history) < 3:
            return {"prediction": "Continue current activity", "confidence": 0.3}

        recent = self._behavior_history[-10:]
        intent_counts: Dict[str, int] = {}
        mood_counts: Dict[str, int] = {}
        for entry in recent:
            intent_counts[entry.get("intent", "general")] = (
                intent_counts.get(entry.get("intent", "general"), 0) + 1
            )
            mood_counts[entry.get("mood", "idle")] = (
                mood_counts.get(entry.get("mood", "idle"), 0) + 1
            )

        dominant_intent = max(intent_counts, key=intent_counts.get)
        dominant_mood = max(mood_counts, key=mood_counts.get)

        prediction_map = {
            "storytelling": "Generate a story based on recent activity",
            "creation": "Open a creative project or editor",
            "research": "Search for information online",
            "design": "Work on visual design or character creation",
            "communication": "Send a message or join a chat",
            "general": "Continue current activity",
        }

        confidence = min(intent_counts[dominant_intent] / len(recent) + 0.2, 0.95)

        return {
            "prediction": prediction_map.get(dominant_intent, "Continue current activity"),
            "dominant_intent": dominant_intent,
            "dominant_mood": dominant_mood,
            "confidence": round(confidence, 3),
            "timeframe": "next 5-10 minutes",
        }

    async def generate_contextual_response(self) -> Dict[str, Any]:
        """Genera respuesta contextual real, no genérica."""
        state = await self.understand_current_state()
        response = ""
        proactive = False

        app = state.active_app.lower()
        intent = state.intent
        mood = state.mood

        if "vscode" in app or "code" in app:
            response = f"Veo que estás programando en {app}. ¿Quieres que genere un personaje para tu proyecto o te ayude con documentación?"
            proactive = True
        elif "anime" in app or "crunchyroll" in app or "tensura" in app:
            response = "¡Interesante! Veo que estás disfrutando anime. ¿Quieres que genere una historia o personaje basado en lo que ves?"
            proactive = True
        elif "browser" in app or "chrome" in app or "search" in app:
            response = "Estás investigando en la web. ¿Necesitas que organice información o generes un resumen?"
            proactive = True
        elif intent == "storytelling":
            response = (
                "Detecto interés en narrativa. ¿Quieres que comience una historia de anime/fantasy?"
            )
            proactive = True
        elif intent == "creation":
            response = "Modo creación activo. ¿Necesitas herramientas o inspiración?"
            proactive = True
        else:
            response = "Hola, soy ARIA. Estoy observando lo que haces. ¿En qué te puedo ayudar?"

        return {
            "response": response,
            "proactive": proactive,
            "state": state.state,
            "confidence": state.confidence,
            "context_used": {
                "intent": intent,
                "mood": mood,
                "app": state.active_app,
            },
        }
