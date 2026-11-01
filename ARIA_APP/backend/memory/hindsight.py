# -*- coding: utf-8 -*-
"""ARIA OS - Hindsight Memory Layer.

Motor de reflexión LLM-dependiente que analiza conversaciones pasadas para
extraer preferencias del usuario, patrones de trabajo y contexto relevante.
Inspirado en Hindsight del video de Wanderloots: memoria más poderosa que
requiere razonamiento LLM para recordar qué se hizo y cómo se hizo.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Memory.Hindsight")


@dataclass
class HindsightInsight:
    """Insight extraído por reflexión sobre el pasado."""
    insight_id: str
    title: str
    description: str
    category: str  # preferencia, patrón, contexto, evitación, herramienta
    confidence: float  # 0.0 a 1.0
    evidence_count: int  # cuántas conversaciones respaldan este insight
    created_at: float = field(default_factory=time.time)
    last_reinforced: float = field(default_factory=time.time)
    source_entries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HindsightReflection:
    """Resultado de una sesión de reflexión."""
    reflection_id: str
    session_id: str
    timestamp: float
    summary: str
    insights_found: List[str]  # insight_ids
    preferences_learned: List[str]
    patterns_identified: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class HindsightMemory:
    """Motor de reflexión LLM-dependiente.

    Analiza el historial de Mnemosyne y LTM para extraer:
    - Preferencias del usuario (cómo le gusta que se hagan las cosas)
    - Patrones de trabajo (herramientas que usa, flujos repetitivos)
    - Contexto de proyectos previos (en qué estaba trabajando antes)
    """

    def __init__(
        self,
        data_dir: str = "data/memory/hindsight",
        llm_provider=None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.llm = llm_provider
        self._insights: Dict[str, HindsightInsight] = {}
        self._reflections: Dict[str, HindsightReflection] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # LLM provider
    # ------------------------------------------------------------------ #
    def set_llm_provider(self, provider) -> None:
        self.llm = provider

    def _has_llm(self) -> bool:
        return self.llm is not None

    # ------------------------------------------------------------------ #
    # Reflexión
    # ------------------------------------------------------------------ #
    def reflect_on_session(
        self,
        session_id: str,
        conversation_text: str,
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> HindsightReflection:
        """Reflexiona sobre una conversación y extrae insights."""
        reflection_id = f"h_{int(time.time() * 1000)}"
        summary = ""
        insights_found: List[str] = []
        preferences_learned: List[str] = []
        patterns_identified: List[str] = []

        if self._has_llm():
            try:
                prompt = self._build_reflection_prompt(conversation_text, context_hints or {})
                response = self._call_llm(prompt)
                parsed = self._parse_reflection_response(response)
                summary = parsed.get("summary") or conversation_text[:200]
                preferences_learned = parsed.get("preferences", [])
                patterns_identified = parsed.get("patterns", [])
                # Convertir preferencias/patrones en insights
                for pref in preferences_learned:
                    iid = self._add_insight(
                        title=pref,
                        description=f"Preferencia aprendida en sesión {session_id}",
                        category="preferencia",
                        confidence=0.7,
                        source_entries=[session_id],
                    )
                    insights_found.append(iid)
                for pat in patterns_identified:
                    iid = self._add_insight(
                        title=pat,
                        description=f"Patrón identificado en sesión {session_id}",
                        category="patrón",
                        confidence=0.6,
                        source_entries=[session_id],
                    )
                    insights_found.append(iid)
            except Exception as exc:
                logger.warning(f"Hindsight: error en reflexión LLM: {exc}")
                summary = conversation_text[:200]
        else:
            summary = conversation_text[:200]
            logger.debug("Hindsight: sin LLM, reflejo básico sin insights")

        reflection = HindsightReflection(
            reflection_id=reflection_id,
            session_id=session_id,
            timestamp=time.time(),
            summary=summary,
            insights_found=insights_found,
            preferences_learned=preferences_learned,
            patterns_identified=patterns_identified,
            metadata=context_hints or {},
        )
        self._reflections[reflection_id] = reflection
        self._save()
        logger.info(f"Hindsight: reflexión {reflection_id} completada ({len(insights_found)} insights)")
        return reflection

    def _build_reflection_prompt(self, text: str, hints: Dict[str, Any]) -> str:
        return (
            "Analiza la siguiente conversación y extrae: "
            "1) Preferencias del usuario (cómo le gusta trabajar, herramientas, formato), "
            "2) Patrones recurrentes (temas que repite, proyectos en curso), "
            "3) Resumen ejecutivo de lo que se logró. "
            "Responde SOLO en JSON con claves: summary, preferences (lista), patterns (lista).\n\n"
            f"CONVERSACIÓN:\n{text[:4000]}\n\n"
            f"CONTEXTO ADICIONAL:\n{json.dumps(hints, ensure_ascii=False)}\n\n"
            "JSON:"
        )

    def _call_llm(self, prompt: str) -> str:
        if hasattr(self.llm, "chat"):
            return self.llm.chat(prompt)
        if hasattr(self.llm, "generate"):
            return self.llm.generate(prompt)
        if hasattr(self.llm, "__call__"):
            return str(self.llm(prompt))
        raise RuntimeError("LLM provider no soporta chat/generate/call")

    @staticmethod
    def _parse_reflection_response(response: str) -> Dict[str, Any]:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception:
            pass
        return {"summary": response[:200], "preferences": [], "patterns": []}

    # ------------------------------------------------------------------ #
    # Insights
    # ------------------------------------------------------------------ #
    def _add_insight(
        self,
        title: str,
        description: str,
        category: str,
        confidence: float,
        source_entries: List[str],
    ) -> str:
        insight_id = hashlib.md5(f"{title}:{time.time()}".encode()).hexdigest()[:16]
        # Si ya existe un insight similar, reforzarlo en lugar de duplicar
        existing = self._find_similar_insight(title, category)
        if existing:
            existing.evidence_count += 1
            existing.last_reinforced = time.time()
            existing.confidence = min(1.0, existing.confidence + 0.05)
            for se in source_entries:
                if se not in existing.source_entries:
                    existing.source_entries.append(se)
            self._save()
            return existing.insight_id

        insight = HindsightInsight(
            insight_id=insight_id,
            title=title,
            description=description,
            category=category,
            confidence=max(0.0, min(1.0, confidence)),
            evidence_count=1,
            source_entries=source_entries,
        )
        self._insights[insight_id] = insight
        self._save()
        return insight_id

    def _find_similar_insight(self, title: str, category: str) -> Optional[HindsightInsight]:
        for ins in self._insights.values():
            if ins.category == category and ins.title.lower() == title.lower():
                return ins
        return None

    def get_insights(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
        top_k: int = 20,
    ) -> List[HindsightInsight]:
        results = [
            ins for ins in self._insights.values()
            if (category is None or ins.category == category)
            and ins.confidence >= min_confidence
        ]
        results.sort(key=lambda i: (i.confidence, i.evidence_count), reverse=True)
        return results[: max(1, top_k)]

    def get_context_for_query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retorna insights relevantes para una consulta del usuario."""
        q_tokens = set(query.lower().split())
        hits: List[Dict[str, Any]] = []
        for ins in self._insights.values():
            t_tokens = set((ins.title + " " + ins.description).lower().split())
            if not q_tokens or not t_tokens:
                continue
            sim = len(q_tokens & t_tokens) / max(1, len(q_tokens | t_tokens))
            if sim > 0:
                hits.append({
                    "insight_id": ins.insight_id,
                    "title": ins.title,
                    "description": ins.description,
                    "category": ins.category,
                    "confidence": ins.confidence,
                    "similarity": round(sim, 4),
                    "source": "hindsight",
                })
        hits.sort(key=lambda h: (h["confidence"], h["similarity"]), reverse=True)
        return hits[: max(1, top_k)]

    def stats(self) -> Dict[str, Any]:
        categories: Dict[str, int] = {}
        for ins in self._insights.values():
            categories[ins.category] = categories.get(ins.category, 0) + 1
        return {
            "total_insights": len(self._insights),
            "total_reflections": len(self._reflections),
            "categories": categories,
            "has_llm": self._has_llm(),
            "data_dir": str(self.data_dir),
        }

    # ------------------------------------------------------------------ #
    # Persistencia
    # ------------------------------------------------------------------ #
    def _save(self) -> None:
        try:
            insights_file = self.data_dir / "insights.json"
            reflections_file = self.data_dir / "reflections.json"
            insights_file.write_text(
                json.dumps([asdict(i) for i in self._insights.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            reflections_file.write_text(
                json.dumps([asdict(r) for r in self._reflections.values()], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Hindsight: error guardando: {exc}")

    def _load(self) -> None:
        insights_file = self.data_dir / "insights.json"
        reflections_file = self.data_dir / "reflections.json"
        if insights_file.exists():
            try:
                raw = json.loads(insights_file.read_text(encoding="utf-8"))
                self._insights = {d["insight_id"]: HindsightInsight(**d) for d in raw}
                logger.info(f"Hindsight: {len(self._insights)} insights cargados")
            except Exception as exc:
                logger.warning(f"Hindsight: error cargando insights: {exc}")
        if reflections_file.exists():
            try:
                raw = json.loads(reflections_file.read_text(encoding="utf-8"))
                self._reflections = {d["reflection_id"]: HindsightReflection(**d) for d in raw}
                logger.info(f"Hindsight: {len(self._reflections)} reflexiones cargadas")
            except Exception as exc:
                logger.warning(f"Hindsight: error cargando reflexiones: {exc}")
