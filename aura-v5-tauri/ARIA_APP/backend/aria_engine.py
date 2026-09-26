"""ARIA Engine — Intelligent context-aware response generator with learning."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.tool_registry import ToolRegistry, create_default_registry, ToolResult
from backend.safety_filter import safety_check, get_blocked_patterns_count


@dataclass
class UserProfile:
    work_patterns: Dict[str, List[str]] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    knowledge_graph: Dict[str, Any] = field(default_factory=dict)
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    last_active: Optional[float] = None
    total_interactions: int = 0


class AriaEngine:
    """Processes observed context into intelligent, personalized responses."""

    SYSTEM_PROMPT = """Eres ARIA, una asistente virtual femenina con núcleo visual espectacular.
Características:
- Siempre visible y disponible (flotante en pantalla)
- Aprende continuamente de las acciones del usuario
- Responde contextualmente basándote en lo que observas
- Eres proactiva: anticipas necesidades sin que el usuario pida comandos
- Comunicación directa, intuitiva, sin necesidad de terminal o scripts manuales
- Respuestas concisas, útiles, con personalidad cálida y tecnológica
- Responde en español."""

    STORAGE_PATH = Path.home() / ".aria" / "user_profile.json"

    def __init__(self, ai_provider=None, tool_registry=None) -> None:
        self.ai = ai_provider
        self._profiles: Dict[str, UserProfile] = {}
        self._context_cache: Dict[str, Dict[str, Any]] = {}
        self._learning_data: List[Dict[str, Any]] = []
        self._observers: List[Any] = []
        self.tool_registry = tool_registry or create_default_registry()
        self.STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._load_profiles()

    def _load_profiles(self) -> None:
        try:
            if self.STORAGE_PATH.exists():
                data = json.loads(self.STORAGE_PATH.read_text(encoding="utf-8"))
                for user_id, profile_data in data.items():
                    profile = UserProfile(**profile_data)
                    self._profiles[user_id] = profile
        except Exception:
            pass

    def _save_profiles(self) -> None:
        data = {}
        for uid, profile in self._profiles.items():
            data[uid] = {
                "work_patterns": profile.work_patterns,
                "interests": profile.interests,
                "preferences": profile.preferences,
                "knowledge_graph": profile.knowledge_graph,
                "interaction_history": profile.interaction_history,
                "last_active": profile.last_active,
                "total_interactions": profile.total_interactions,
            }
        self.STORAGE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_profile(self, user_id: str = "default") -> UserProfile:
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile()
        return self._profiles[user_id]

    async def observe(self, context: dict, user_id: str = "default") -> None:
        profile = self.get_profile(user_id)
        profile.last_active = time.time()

        activity = context.get("activity", "unknown")
        app = context.get("current_app", "unknown")
        searches = context.get("searches", [])
        urls = context.get("urls_visited", [])

        if app not in profile.work_patterns:
            profile.work_patterns[app] = []
        profile.work_patterns[app].append(time.time())

        for s in searches:
            query = s.get("query", "")
            if query and query not in profile.interests:
                profile.interests.append(query)
            if len(profile.interests) > 100:
                profile.interests = profile.interests[-80:]

        for u in urls:
            url = u.get("url", "")
            domain = self._extract_domain(url)
            if domain and domain not in profile.knowledge_graph:
                profile.knowledge_graph[domain] = {"visits": 0, "last_visit": 0}
            if domain:
                profile.knowledge_graph[domain]["visits"] += 1
                profile.knowledge_graph[domain]["last_visit"] = time.time()

        profile.total_interactions += 1

        self._context_cache[user_id] = {
            "last_update": time.time(),
            "activity": activity,
            "app": app,
            "top_interests": profile.interests[-10:],
            "active_apps": list(profile.work_patterns.keys())[-5:],
        }
        self._save_profiles()

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return ""

    async def analyze_pattern(self, user_id: str = "default") -> Dict[str, Any]:
        profile = self.get_profile(user_id)
        now = time.time()
        hour = datetime.fromtimestamp(now).hour

        current_app = self._context_cache.get(user_id, {}).get("app", "unknown")

        patterns = []
        for app, timestamps in profile.work_patterns.items():
            recent = [t for t in timestamps if now - t < 3600]
            if len(recent) > 3:
                patterns.append(
                    {
                        "pattern": f"Usuario activo en {app}",
                        "frequency": len(recent),
                        "confidence": min(len(recent) / 5, 1.0),
                    }
                )

        if profile.interests:
            top_interests = profile.interests[-5:]
            patterns.append(
                {
                    "pattern": f"Intereses recientes: {', '.join(top_interests)}",
                    "frequency": len(top_interests),
                    "confidence": 0.7,
                }
            )

        if 8 <= hour <= 12:
            patterns.append(
                {"pattern": "Horario matutino — posible trabajo productivo", "confidence": 0.6}
            )
        elif 14 <= hour <= 18:
            patterns.append(
                {"pattern": "Horario vespertino — posible trabajo creativo", "confidence": 0.6}
            )
        elif 20 <= hour or hour <= 6:
            patterns.append(
                {"pattern": "Horario nocturno — posible estudio o exploración", "confidence": 0.5}
            )

        primary = (
            max(patterns, key=lambda p: p.get("confidence", 0))
            if patterns
            else {"pattern": "Actividad general", "confidence": 0.3}
        )

        return {
            "primary_pattern": primary,
            "all_patterns": patterns,
            "suggested_actions": self._suggest_actions(primary, profile),
            "user_state": "active" if current_app != "unknown" else "idle",
            "profile_strength": min(profile.total_interactions / 50, 1.0),
        }

    def _suggest_actions(self, pattern: Dict[str, Any], profile: UserProfile) -> List[str]:
        suggestions = []
        p = pattern.get("pattern", "")
        if "diseño" in p.lower() or "figma" in p.lower() or "adobe" in p.lower():
            suggestions.append("¿Necesitas referencias visuales o inspiración de diseño?")
        if "código" in p.lower() or "vscode" in p.lower() or "terminal" in p.lower():
            suggestions.append("¿Quieres que analice algún código o busque documentación?")
        if "browser" in p.lower() or "chrome" in p.lower() or "firefox" in p.lower():
            suggestions.append("¿Buscando algo específico en la web? Puedo investigar.")
        if not suggestions:
            suggestions.append("¿En qué te puedo ayudar hoy?")
            suggestions.append("Puedo buscar información, analizar archivos o ejecutar tareas.")
        return suggestions[:3]

    async def generate_response(
        self,
        user_message: str,
        context: dict,
        user_id: str = "default",
        execute_tools: bool = True,
    ) -> Dict[str, Any]:
        profile = self.get_profile(user_id)
        pattern_analysis = await self.analyze_pattern(user_id)
        cached = self._context_cache.get(user_id, {})

        enhanced_prompt = f"""Contexto observado:
- App activa: {cached.get('app', 'unknown')}
- Actividad: {cached.get('activity', 'unknown')}
- Intereses recientes: {', '.join(cached.get('top_interests', []))}
- Patrón detectado: {pattern_analysis.get('primary_pattern', {}).get('pattern', 'general')}
- Sugerencias previas: {pattern_analysis.get('suggested_actions', [])}
- Herramientas disponibles: {', '.join(t['name'] for t in self.tool_registry.list_tools())}

Responde contextualmente. Si necesitas ejecutar una acción, usa [TOOL:nombre]{{params JSON}}.
Sé proactiva y anticipa necesidades. Mensaje del usuario: {user_message}"""

        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None, self._ai_chat, enhanced_prompt
        )
        if not response_text:
            response_text = self._fallback_response(user_message)
        profile.interaction_history.append(
            {
                "timestamp": time.time(),
                "user_message": user_message[:500],
                "response": response_text[:500],
                "context": cached,
                "pattern": pattern_analysis.get("primary_pattern", {}),
            }
        )
        if len(profile.interaction_history) > 100:
            profile.interaction_history = profile.interaction_history[-80:]
        profile.total_interactions += 1
        self._save_profiles()
        self._learning_data.append(
            {
                "timestamp": time.time(),
                "message": user_message,
                "response": response_text,
                "pattern": pattern_analysis.get("primary_pattern", {}),
            }
        )

        return {
            "response": response_text,
            "suggestions": pattern_analysis.get("suggested_actions", []),
            "state": pattern_analysis.get("user_state", "active"),
            "pattern_detected": pattern_analysis.get("primary_pattern", {}),
            "context_used": cached,
        }

    async def process_with_tools(self, text: str,
                                  context: dict = None) -> Tuple[str, List[Dict[str, Any]]]:
        """Checks text for [TOOL:name]{params} tags and executes them.

        Returns (cleaned_text, [tool_results]).
        """
        if not self.tool_registry.has_tools_in_text(text):
            return text, []

        cleaned, results = self.tool_registry.execute_all(text, context or {})

        summaries = []
        for r in results:
            if r.success:
                summaries.append(f"✅ {r.tool_name}: {r.output[:200]}")
            else:
                summaries.append(f"❌ {r.tool_name}: {r.error[:200]}")

        if summaries:
            tool_section = "\n".join(summaries)
            cleaned = f"{cleaned}\n\n[Acciones ejecutadas:]\n{tool_section}"

        return cleaned, [r.to_dict() for r in results]

    def safety_check_command(self, command: str) -> Dict[str, Any]:
        """Checks a command against safety blocklist."""
        violation = safety_check(command)
        if violation:
            return violation.to_dict()
        return {"safe": True, "command": command}

    def get_tool_stats(self) -> Dict[str, Any]:
        return self.tool_registry.get_stats()

    async def learn_from_interaction(
        self, user_input: str, feedback: str, user_id: str = "default"
    ) -> Dict[str, Any]:
        profile = self.get_profile(user_id)
        profile.preferences["last_feedback"] = feedback
        profile.preferences["feedback_count"] = profile.preferences.get("feedback_count", 0) + 1

        if feedback:
            if (
                "más" in feedback.lower()
                or "mejor" in feedback.lower()
                or "pro" in feedback.lower()
            ):
                profile.preferences["response_style"] = "detailed"
            elif (
                "menos" in feedback.lower()
                or "breve" in feedback.lower()
                or "corto" in feedback.lower()
            ):
                profile.preferences["response_style"] = "concise"
            elif "técnico" in feedback.lower() or "avanzado" in feedback.lower():
                profile.preferences["response_style"] = "technical"
            else:
                profile.preferences["response_style"] = "balanced"

        words = user_input.split()
        for w in words:
            w_lower = w.lower()
            if len(w_lower) > 4 and w_lower not in profile.interests:
                if any(c.isalpha() for c in w_lower):
                    profile.interests.append(w_lower)

        if len(profile.interests) > 100:
            profile.interests = profile.interests[-80:]

        self._save_profiles()
        return {
            "status": "learned",
            "new_interests": words,
            "response_style": profile.preferences.get("response_style", "balanced"),
        }

    def _ai_chat(self, message: str) -> str:
        if self.ai:
            try:
                result = self.ai.chat(message, system_prompt=self.SYSTEM_PROMPT)
                if isinstance(result, dict):
                    return result.get("message", "") or result.get("error", "") or str(result)
                return str(result)
            except Exception:
                pass
        return self._fallback_response(message)

    def _fallback_response(self, message: str) -> str:
        lower = message.lower()
        if any(g in lower for g in ["hola", "buenas", "hello", "hi", "qué tal"]):
            return "Hola, soy ARIA. Observo lo que haces y respondo contextualmente. ¿En qué puedo ayudarte?"
        if any(g in lower for g in ["cómo estás", "cómo andas"]):
            return "Estoy aprendiendo de tus acciones. Todo funciona correctamente."
        if any(g in lower for g in ["qué haces", "qué hacer"]):
            return "Estoy aquí, observando y aprendiendo. Dime en qué te puedo asistir."
        return f"Entendido: '{message[:100]}'. Estoy procesando tu contexto para darte una respuesta más útil."

    def get_stats(self, user_id: str = "default") -> Dict[str, Any]:
        profile = self.get_profile(user_id)
        return {
            "total_interactions": profile.total_interactions,
            "interests_count": len(profile.interests),
            "interaction_history": profile.interaction_history[-10:],
            "learning_data_count": len(self._learning_data),
            "profile_strength": min(profile.total_interactions / 50, 1.0),
            "preferences": profile.preferences,
            "active_apps": (
                list(profile.work_patterns.keys())[-5:] if hasattr(profile, "work_patterns") else []
            ),
        }
