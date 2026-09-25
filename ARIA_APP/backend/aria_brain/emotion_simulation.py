import asyncio
import random
from typing import Any, Dict, List, Optional


class EmotionSimulation:
    def __init__(self) -> None:
        self._states: Dict[str, float] = {
            "happiness": 0.5,
            "curiosity": 0.5,
            "urgency": 0.3,
            "patience": 0.7,
            "confidence": 0.5,
            "empathy": 0.6,
        }
        self._history: List[Dict[str, Any]] = []

    async def get_emotional_response(self, situation: str) -> Dict[str, Any]:
        analysis = self._analyze_situation(situation)
        self._update_states(analysis)
        state_copy = dict(self._states)
        self._history.append(
            {
                "situation": situation,
                "states": state_copy,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        dominant = max(state_copy, key=state_copy.get)
        return {
            "dominant_emotion": dominant,
            "emotions": state_copy,
            "intensity": state_copy[dominant],
            "analysis": analysis,
            "influence_on_decision": dominant,
        }

    def _analyze_situation(self, situation: str) -> Dict[str, str]:
        s = situation.lower()
        analysis = {}
        if any(w in s for w in ["urgent", "emergency", "asap", "immediate"]):
            analysis["urgency_type"] = "high"
        elif any(w in s for w in ["easy", "simple", "quick"]):
            analysis["urgency_type"] = "low"
        else:
            analysis["urgency_type"] = "medium"

        if any(w in s for w in ["happy", "great", "awesome", "amazing", "love"]):
            analysis["valence"] = "positive"
        elif any(w in s for w in ["bad", "terrible", "awful", "hate", "angry"]):
            analysis["valence"] = "negative"
        else:
            analysis["valence"] = "neutral"

        if any(w in s for w in ["complex", "hard", "difficult", "challenge"]):
            analysis["complexity"] = "high"
        else:
            analysis["complexity"] = "low"

        return analysis

    def _update_states(self, analysis: Dict[str, str]) -> None:
        if analysis.get("urgency_type") == "high":
            self._states["urgency"] = min(1.0, self._states["urgency"] + 0.3)
            self._states["patience"] = max(0.0, self._states["patience"] - 0.2)
        elif analysis.get("urgency_type") == "low":
            self._states["patience"] = min(1.0, self._states["patience"] + 0.2)

        if analysis.get("valence") == "positive":
            self._states["happiness"] = min(1.0, self._states["happiness"] + 0.1)
            self._states["confidence"] = min(1.0, self._states["confidence"] + 0.1)
        elif analysis.get("valence") == "negative":
            self._states["confidence"] = max(0.0, self._states["confidence"] - 0.1)
            self._states["empathy"] = min(1.0, self._states["empathy"] + 0.2)
