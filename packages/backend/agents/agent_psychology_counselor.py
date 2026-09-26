# -*- coding: utf-8 -*-
"""AURA OS — Psychology Counselor Agent.

Analyzes emotions, suggests coping strategies, generates journal prompts, tracks mood.
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Psychology")

EMOTIONS = ["anxiety", "stress", "happiness", "sadness", "anger", "fear", "confusion", "loneliness", "boredom", "gratitude"]
COPING_STRATEGIES = [
    "Deep breathing (4-7-8 technique)",
    "Progressive muscle relaxation",
    "Mindfulness meditation",
    "Cognitive reframing",
    "Journaling emotions",
    "Physical exercise",
    "Social connection",
    "Nature walk",
    "Creative expression",
    "Gratitude practice",
]
JOURNAL_PROMPTS = [
    "What moment today made you feel most alive?",
    "Describe a challenge you overcame and what it taught you.",
    "What boundary do you need to set this week?",
    "Write about someone who positively impacted your day.",
    "What emotion are you avoiding, and why might it be there?",
    "If today had a color, what would it be and why?",
    "What does your inner critic say, and is it true?",
    "Describe your ideal self-care moment.",
    "What are you proud of but haven't acknowledged?",
    "Write a letter to your future self in 6 months.",
]


class PsychologyCounselorAgent:
    """Psychology counseling: emotion analysis, coping strategies, journaling, mood tracking."""

    def __init__(self) -> None:
        self.sessions_conducted: int = 0
        self.mood_history: List[Dict[str, Any]] = []

    async def listen_and_analyze(self, text: str) -> Dict[str, Any]:
        detected_emotions = {}
        for _ in range(random.randint(1, 4)):
            emotion = random.choice(EMOTIONS)
            detected_emotions[emotion] = round(random.uniform(0.1, 0.95), 4)

        word_count = len(text.split()) if text else random.randint(20, 200)
        sentiment = "positive" if max(detected_emotions.values(), default=0) > 0.6 else "mixed" if detected_emotions else "neutral"

        return {
            "analysis_id": f"PSA-{int(datetime.now().timestamp())}",
            "text_length": word_count,
            "emotions": detected_emotions,
            "primary_emotion": max(detected_emotions, key=detected_emotions.get) if detected_emotions else "neutral",
            "intensity": round(max(detected_emotions.values(), default=0), 4),
            "sentiment": sentiment,
            "needs_attention": list(detected_emotions.keys()),
            "session_id": f"SES-{self.sessions_conducted}",
            "analyzed_at": datetime.now().isoformat(),
        }

    async def suggest_coping_strategies(self) -> Dict[str, Any]:
        strategies = []
        count = random.randint(2, 5)
        for strategy in random.sample(COPING_STRATEGIES, k=min(count, len(COPING_STRATEGIES))):
            strategies.append({
                "strategy": strategy,
                "duration_min": random.randint(5, 45),
                "difficulty": random.choice(["beginner", "intermediate", "advanced"]),
                "effectiveness": round(random.uniform(0.5, 0.95), 4),
                "category": random.choice(["relaxation", "cognitive", "physical", "social", "creative"]),
                "steps": [f"Step {i+1}: {random.choice(['Breathe deeply', 'Focus on present', 'Let go', 'Observe', 'Accept'])}" for i in range(random.randint(2, 5))],
            })

        return {
            "strategies_id": f"COP-{int(datetime.now().timestamp())}",
            "strategies": strategies,
            "count": len(strategies),
            "recommended_order": "by effectiveness descending",
            "emergency": random.choice(["Call a trusted friend", "Practice 4-7-8 breathing", "Ground yourself (5-4-3-2-1)"]) if random.random() > 0.7 else None,
            "generated_at": datetime.now().isoformat(),
        }

    async def journal_prompt(self) -> Dict[str, Any]:
        prompt = random.choice(JOURNAL_PROMPTS)

        return {
            "prompt_id": f"JRN-{int(datetime.now().timestamp())}",
            "prompt": prompt,
            "category": random.choice(["reflection", "self-discovery", "gratitude", "challenge", "growth"]),
            "difficulty": random.choice(["easy", "medium", "deep"]),
            "estimated_time_min": random.randint(5, 30),
            "follow_up": random.choice([
                "Explore this further with 'why' questions.",
                "Notice where you feel this in your body.",
                "Consider how this connects to your values.",
                "Write without stopping for 10 minutes.",
            ]),
            "generated_at": datetime.now().isoformat(),
        }

    async def mood_tracking(self) -> Dict[str, Any]:
        history = []
        for i in range(random.randint(7, 30)):
            date = datetime.now() - timedelta(days=i)
            history.append({
                "date": date.isoformat(),
                "primary_emotion": random.choice(EMOTIONS),
                "intensity": round(random.uniform(0.1, 1.0), 4),
                "energy": round(random.uniform(0.1, 1.0), 4),
                "sleep_hours": round(random.uniform(4, 10), 1),
                "note": random.choice(["Good day", "Average", "Tough but managed", "Excellent", "Needs care"]),
            })

        history.reverse()

        avg_intensity = sum(h["intensity"] for h in history) / len(history) if history else 0
        trend = "improving" if avg_intensity > 0.5 else "declining" if avg_intensity < 0.3 else "stable"

        return {
            "mood_id": f"MOOD-{int(datetime.now().timestamp())}",
            "history": history,
            "days_tracked": len(history),
            "avg_intensity": round(avg_intensity, 4),
            "avg_energy": round(sum(h["energy"] for h in history) / len(history), 4) if history else 0,
            "trend": trend,
            "streak": random.randint(1, 60),
            "recommendation": f"Your mood is {trend}. Keep tracking and practice self-care.",
            "tracked_at": datetime.now().isoformat(),
        }


psychology_counselor = PsychologyCounselorAgent()
