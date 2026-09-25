"""PARTE 5: CONTEXTUAL ENGINE ADVANCED (400 lines) — Comprensión contextual extrema.

Funciones async:
- understand_current_state_advanced(): screen + audio + observer + history
- proactive_suggestions(): predicciones anticipadas
- emotional_tone_detection(): mood desde velocidad, audio, búsquedas
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
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from backend.monitoring.screen_analyzer_pro import (
        capture_screen_optimized,
        detect_visual_changes_fast,
        extract_text_ocr_advanced,
        semantic_understanding_advanced,
    )

    HAS_SCREEN_PRO = True
except ImportError:
    HAS_SCREEN_PRO = False

try:
    from backend.monitoring.audio_analyzer_pro import (
        detect_audio_advanced,
        music_analysis,
        speech_recognition_streaming,
    )

    HAS_AUDIO_PRO = True
except ImportError:
    HAS_AUDIO_PRO = False

try:
    from backend.aria_observer_v2 import AriaObserverV2

    HAS_OBSERVER = True
except ImportError:
    HAS_OBSERVER = False

try:
    from backend.aria_brain import AriaBrain

    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

try:
    from backend.monitoring.background_learning_pro import BackgroundLearningDaemon

    HAS_LEARNING = True
except ImportError:
    HAS_LEARNING = False


@dataclass
class ContextState:
    state: str = "unknown"
    confidence: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    activity_type: str = "unknown"
    mood: str = "idle"
    intent: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    emotional_tone: str = "neutral"
    emotional_intensity: float = 0.0
    predicted_next_actions: List[str] = field(default_factory=list)
    session_duration: float = 0.0


@dataclass
class ProactiveSuggestion:
    prediction: str = ""
    confidence: float = 0.0
    suggested_action: str = ""
    timeframe: str = ""
    priority: str = "medium"
    category: str = "general"


@dataclass
class EmotionalTone:
    tone: str = "neutral"
    intensity: float = 0.0
    indicators: Dict[str, float] = field(default_factory=dict)
    recommendation: str = "Continue normally"


class ContextualEngineAdvanced:
    """Comprensión contextual extrema: fusiona TODO."""

    ACTIVITY_MAP = {
        "code_editor": "coding",
        "web_browser": "research",
        "video_streaming": "media_consumption",
        "social_media": "social_browsing",
        "email": "communication",
        "document_editor": "document_work",
        "gaming": "entertainment",
        "anime_viewing": "media_consumption",
        "terminal": "system_ops",
        "content_exploration": "research",
        "general_desktop": "idle",
    }

    MOOD_MAP = {
        "exploring": "curious",
        "creating": "focused",
        "relaxed": "relaxed",
        "stressed": "stressed",
        "excited": "excited",
        "frustrated": "frustrated",
    }

    def __init__(self):
        self.screen_data: Dict[str, Any] = {}
        self.audio_data: Dict[str, Any] = {}
        self.observer_data: Dict[str, Any] = {}
        self.brain: Optional[Any] = None
        self.learning: Optional[BackgroundLearningDaemon] = None

        if HAS_BRAIN:
            try:
                self.brain = AriaBrain(ai_manager=None)
            except Exception:
                self.brain = None
        if HAS_LEARNING:
            try:
                self.learning = BackgroundLearningDaemon()
            except Exception:
                self.learning = None

        self._history: List[Dict[str, Any]] = []
        self._session_start: float = time.time()
        self._typing_speed: float = 0.0
        self._pause_duration: float = 0.0
        self._search_count: int = 0
        self._lock = asyncio.Lock()

    async def understand_current_state_advanced(self) -> ContextState:
        """Fusión completa: screen + audio + observer + history."""
        async with self._lock:
            screen_result = {}
            audio_result = {}
            observer_result = {}

            if HAS_SCREEN_PRO:
                try:
                    capture = await capture_screen_optimized()
                    ocr = await extract_text_ocr_advanced(capture.image)
                    changes = await detect_visual_changes_fast(capture.image)
                    semantic = await semantic_understanding_advanced(
                        image=capture.image,
                        ocr_text=ocr.get("text", ""),
                        active_app=capture.active_app,
                    )
                    screen_result = {
                        "active_app": capture.active_app,
                        "ocr_text": ocr.get("text", ""),
                        "language": ocr.get("language", "mixed"),
                        "ocr_confidence": ocr.get("confidence", 0.0),
                        "changed": changes.get("changed", False),
                        "change_regions": changes.get("regions", []),
                        "change_intensity": changes.get("intensity", 0.0),
                        "semantic": semantic,
                        "timestamp": capture.timestamp,
                    }
                except Exception as e:
                    screen_result = {"error": str(e), "active_app": "unknown"}

            if HAS_AUDIO_PRO:
                try:
                    audio = await detect_audio_advanced()
                    speech = await speech_recognition_streaming()
                    music = await music_analysis()
                    audio_result = {
                        "detected": audio.audio_detected,
                        "volume": audio.volume,
                        "type": audio.type,
                        "bpm": audio.beats_per_minute,
                        "frequency_bands": audio.frequency_bands,
                        "speech": speech.transcription,
                        "speech_confidence": speech.speech_confidence,
                        "speech_language": speech.language,
                        "is_command": speech.is_command,
                        "music_genre": music.genre,
                        "music_bpm": music.bpm,
                        "music_mood": music.mood,
                    }
                except Exception as e:
                    audio_result = {"error": str(e)}

            if HAS_OBSERVER:
                try:
                    observer = AriaObserverV2(poll_interval=1)
                    intent = await observer.detect_intent()
                    mood = await observer.track_mood()
                    keywords = await observer.extract_context_keywords()
                    suggestions = await observer.suggest_based_on_context()
                    observer_result = {
                        "intent": intent,
                        "mood": mood,
                        "keywords": keywords,
                        "suggestions": suggestions,
                    }
                except Exception as e:
                    observer_result = {"error": str(e)}

            if self.brain and HAS_BRAIN:
                try:
                    brain_state = self.brain.think_and_decide(
                        "context_request",
                        context_data={
                            "screen": screen_result,
                            "audio": audio_result,
                            "observer": observer_result,
                        },
                    )
                    observer_result["brain_state"] = brain_state
                except Exception:
                    pass

            active_app = screen_result.get("active_app", "unknown")
            activity_type = self.ACTIVITY_MAP.get(
                screen_result.get("semantic", {}).get("scene_type", "unknown"), "idle"
            )
            intent = observer_result.get("intent", {}).get("intent", "general")
            mood = observer_result.get("mood", {}).get("mood", "idle")

            all_suggestions = self._generate_all_suggestions(
                intent, mood, activity_type, screen_result, audio_result, observer_result
            )

            confidence = self._calc_confidence(screen_result, audio_result, observer_result)

            emotional = await self.emotional_tone_detection(
                screen_result, audio_result, observer_result
            )

            predicted = await self._predict_next_actions(
                activity_type, intent, mood, screen_result, audio_result
            )

            state = ContextState(
                state=screen_result.get("semantic", {}).get("understanding", f"Using {active_app}"),
                confidence=confidence,
                details={
                    "screen": screen_result,
                    "audio": audio_result,
                    "observer": observer_result,
                },
                activity_type=activity_type,
                mood=mood,
                intent=intent,
                context={
                    "active_app": active_app,
                    "activity": activity_type,
                    "scene": screen_result.get("semantic", {}).get("scene_type", "unknown"),
                },
                suggestions=all_suggestions,
                emotional_tone=emotional.tone,
                emotional_intensity=emotional.intensity,
                predicted_next_actions=predicted,
                session_duration=time.time() - self._session_start,
            )

            self._history.append(
                {
                    "timestamp": time.time(),
                    "state": state.state,
                    "intent": intent,
                    "mood": mood,
                    "activity": activity_type,
                    "app": active_app,
                    "confidence": confidence,
                }
            )
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

            if self.learning and HAS_LEARNING:
                try:
                    await self.learning.record_event(
                        {
                            "type": "context_update",
                            "activity": activity_type,
                            "intent": intent,
                            "mood": mood,
                            "app": active_app,
                            "timestamp": time.time(),
                        }
                    )
                except Exception:
                    pass

            return state

    async def proactive_suggestions(self, count: int = 5) -> List[ProactiveSuggestion]:
        """Sugerencias proactivas basadas en estado actual."""
        try:
            state = await self.understand_current_state_advanced()
        except Exception:
            return []

        suggestions: List[ProactiveSuggestion] = []
        intent = state.intent
        mood = state.mood
        activity = state.activity_type
        app = state.context.get("active_app", "").lower()

        suggestion_templates = [
            ProactiveSuggestion(
                prediction="Generar contenido creativo",
                confidence=0.8,
                suggested_action="Crear story/character basado en actividad actual",
                timeframe="inmediato",
                priority="high",
                category="creation",
            ),
            ProactiveSuggestion(
                prediction="Búsqueda de información relevante",
                confidence=0.7,
                suggested_action="Investigar tema relacionado con intención actual",
                timeframe="2-5 minutos",
                priority="medium",
                category="discovery",
            ),
            ProactiveSuggestion(
                prediction="Modo de concentración profundo",
                confidence=0.6,
                suggested_action="Activar focus mode, silenciar notificaciones",
                timeframe="ahora",
                priority="high",
                category="productivity",
            ),
            ProactiveSuggestion(
                prediction="Descanso y recuperación",
                confidence=0.5,
                suggested_action="Pausa de 5 min, estiramientos, hidratación",
                timeframe="próximos 15 min",
                priority="medium",
                category="wellness",
            ),
            ProactiveSuggestion(
                prediction="Organización de ideas",
                confidence=0.65,
                suggested_action="Revisar notas y organizar conocimiento",
                timeframe="próximos 10 min",
                priority="low",
                category="organization",
            ),
        ]

        for s in suggestion_templates:
            if intent == "storytelling" and "creation" in s.category:
                s.confidence = min(s.confidence + 0.15, 0.95)
                s.prediction = "Generar historia/anime basada en tu actividad"
            elif intent == "design" and "creation" in s.category:
                s.confidence = min(s.confidence + 0.15, 0.95)
                s.prediction = "Crear personaje/diseño basado en referencias"
            elif intent == "creation" and "creation" in s.category:
                s.confidence = min(s.confidence + 0.1, 0.9)
            elif intent == "research" and "discovery" in s.category:
                s.confidence = min(s.confidence + 0.2, 0.95)
            elif activity == "coding" and "productivity" in s.category:
                s.confidence = min(s.confidence + 0.15, 0.9)

            if mood == "stressed":
                if "wellness" in s.category:
                    s.priority = "high"
                    s.confidence = min(s.confidence + 0.2, 0.95)
            elif mood == "focused":
                if "productivity" in s.category:
                    s.priority = "high"
                    s.confidence = min(s.confidence + 0.15, 0.9)

            suggestions.append(s)

        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return suggestions[:count]

    async def emotional_tone_detection(
        self,
        screen: Dict[str, Any] = None,
        audio: Dict[str, Any] = None,
        observer: Dict[str, Any] = None,
    ) -> EmotionalTone:
        """Detección de tono emocional multidimensional."""
        indicators: Dict[str, float] = {}
        tone = "neutral"
        intensity = 0.0

        volume = audio.get("volume", 0) if audio else 0
        audio_type = audio.get("type", "unknown") if audio else "unknown"
        speech = audio.get("speech", "") if audio else ""
        typing_speed = getattr(self, "_typing_speed", 0.0)
        pause_duration = getattr(self, "_pause_duration", 0.0)
        search_count = getattr(self, "_search_count", 0)
        mood_observer = observer.get("mood", {}) if observer else {}
        intent_observer = observer.get("intent", {}) if observer else {}

        if volume > 70:
            indicators["volume_high"] = 0.9
        elif volume > 40:
            indicators["volume_medium"] = 0.6
        else:
            indicators["volume_low"] = 0.3

        if audio_type == "loud_audio":
            indicators["loud_env"] = 0.7
        elif audio_type == "music_playing":
            indicators["music"] = 0.5

        active_app = screen.get("active_app", "").lower() if screen else ""
        semantic = screen.get("semantic", {}) if screen else {}
        scene_type = semantic.get("scene_type", "unknown") if semantic else "unknown"

        if "code" in active_app or "vscode" in active_app or "terminal" in active_app:
            indicators["coding_focus"] = 0.7
            if typing_speed > 5.0:
                indicators["fast_typing"] = min(typing_speed / 10.0, 1.0)
            elif typing_speed < 1.0:
                indicators["slow_typing"] = min((1.0 - typing_speed), 0.5)
        elif "browser" in active_app or "search" in active_app:
            indicators["researching"] = 0.6
        elif "anime" in active_app or "crunchyroll" in active_app:
            indicators["relaxed_viewing"] = 0.6

        if pause_duration > 5.0:
            indicators["long_pause"] = min(pause_duration / 30.0, 1.0)
        elif pause_duration > 2.0:
            indicators["medium_pause"] = 0.5

        if mood_observer.get("mood"):
            mood_val = mood_observer.get("mood")
            intensity_val = mood_observer.get("intensity", 0)
            indicators[f"observer_mood_{mood_val}"] = min(intensity_val / 100.0, 1.0)

        if intent_observer.get("intent"):
            intent_val = intent_observer.get("intent")
            indicators[f"intent_{intent_val}"] = intent_observer.get("confidence", 0.3)

        if speech:
            speech_lower = speech.lower()
            if any(w in speech_lower for w in ["feliz", "contento", "happy", "great"]):
                indicators["happy_speech"] = 0.8
                tone = "happy"
            elif any(w in speech_lower for w in ["triste", "sad", "depressed"]):
                indicators["sad_speech"] = 0.8
                tone = "sad"
            elif any(w in speech_lower for w in ["enojado", "angry", "frustrated"]):
                indicators["angry_speech"] = 0.8
                tone = "angry"
            elif any(w in speech_lower for w in ["estresado", "stressed"]):
                indicators["stressed_speech"] = 0.8
                tone = "stressed"

        intensity = sum(indicators.values()) / max(len(indicators), 1)

        if not tone or tone == "neutral":
            if "observer_mood_creating" in indicators:
                tone = "focused"
            elif "observer_mood_exploring" in indicators:
                tone = "curious"
            elif "observer_mood_relaxing" in indicators:
                tone = "relaxed"
            elif "stressed" in str(indicators).lower():
                tone = "stressed"
            elif intensity > 0.6:
                tone = "engaged"
            else:
                tone = "relaxed"

        recommendations = {
            "happy": "Excelente energía! Aprovecha para crear algo grande.",
            "sad": "Parece que no estás al 100%. ¿Quieres que busque algo inspirador?",
            "angry": "Detecto frustración. Tomate un descanso o hagamos algo productivo.",
            "stressed": "Alto nivel de estrés. Pausa recomendada: 5 minutos de respiración.",
            "focused": "¡Gran concentración! No interrumpas el flujo.",
            "curious": "Modo exploración activo. Ideal para descubrir cosas nuevas.",
            "relaxed": "Ambiente tranquilo. Perfecto para tareas creativas.",
            "engaged": "Estás muy activo. ¿Quieres que organice tus ideas?",
            "neutral": "Estado normal. Operando en modo estándar.",
        }

        return EmotionalTone(
            tone=tone,
            intensity=round(min(intensity, 1.0), 3),
            indicators=dict(list(indicators.items())[:10]),
            recommendation=recommendations.get(tone, recommendations["neutral"]),
        )

    def _generate_all_suggestions(
        self, intent, mood, activity, screen, audio, observer
    ) -> List[str]:
        suggestions = []
        if intent in ("storytelling", "design"):
            suggestions.append(f"Story Mode: Genera contenido sobre {intent}")
        if intent in ("creation",):
            suggestions.append("Create Mode: Inicia un nuevo proyecto")
        if intent == "research":
            suggestions.append("Research Mode: Busca información relevante")
        if mood == "exploring":
            suggestions.append("Explore: Descubre nuevos temas")
        if mood == "focused":
            suggestions.append("Focus: Mantén la concentración, gran momento")
        if mood == "stressed":
            suggestions.append("Wellness: Tómate un descanso de 5 min")
        if audio and audio.get("music_playing", False) if audio else False:
            suggestions.append("Music: Sigue escuchando")
        if activity == "coding":
            suggestions.append("Code Helper: ¿Necesitas ayuda con el código?")
        if activity == "gaming":
            suggestions.append("Game Mode: ¿Quieres consejos para mejorar?")
        return suggestions[:6]

    def _calc_confidence(self, screen: Dict, audio: Dict, observer: Dict) -> float:
        score = 0.1
        if screen.get("active_app") and screen["active_app"] != "unknown":
            score += 0.2
        if screen.get("ocr_confidence", 0) > 0.3:
            score += 0.15
        if (
            observer.get("intent", {}).get("intent")
            and observer["intent"].get("intent") != "general"
        ):
            score += 0.2
        if observer.get("mood", {}).get("mood") and observer["mood"].get("mood") != "idle":
            score += 0.15
        if audio.get("detected") is not None and audio.get("detected", False):
            score += 0.1
        if (
            screen.get("semantic", {}).get("scene_type")
            and screen["semantic"]["scene_type"] != "unknown"
        ):
            score += 0.15
        if audio.get("speech_confidence", 0) > 0.3:
            score += 0.1
        return min(score, 1.0)

    async def _predict_next_actions(self, activity, intent, mood, screen, audio) -> List[str]:
        predictions = []
        if intent == "storytelling":
            predictions.append("Generar personaje/anime en 2 minutos")
            predictions.append("Mundo fantasy: crear mapa y lore")
        elif intent == "creation":
            predictions.append("Abrir editor/IDE para siguiente proyecto")
            predictions.append("Refactorizar código existente")
        elif intent == "research":
            predictions.append("Búsqueda profunda sobre tema actual")
            predictions.append("Organizar notas de investigación")
        elif intent == "design":
            predictions.append("Buscar referencias visuales")
            predictions.append("Crear moodboard del proyecto")
        else:
            predictions.append("Continuar actividad actual")

        if mood == "focused":
            predictions.insert(0, "¡Mantén el focus! Eres productivo ahora")
        elif mood == "exploring":
            predictions.append("Explorar nuevas herramientas/ideas")
        elif mood == "stressed":
            predictions.append("Pausa de bienestar recomendada")

        return predictions[:4]
