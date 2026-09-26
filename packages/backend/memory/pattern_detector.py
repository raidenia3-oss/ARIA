# -*- coding: utf-8 -*-
"""AURA OS - Chunk 3: Patrón Detector.

Detecta patrones en acciones del sistema y guarda:
- 'Cuando pide X, prefiere Y'
- Actualiza grafo cognitivo con new patrones
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.memory.manager import get_memory_manager

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------

PATTERNS_FILE = Path('data/memory/patterns.json')
MIN_OBSERVATIONS = 3
CONFIDENCE_THRESHOLD = 0.7
PATTERN_LIFETIME_HOURS = 24


class Pattern:
    """Patrón detectado: cuando se observa X, se prefiere Y."""

    def __init__(
        self,
        trigger: str,
        preference: str,
        observations: int = 0,
        confidence: float = 0.0,
        first_seen: Optional[float] = None,
        last_seen: Optional[float] = None,
    ):
        self.trigger = trigger
        self.preference = preference
        self.observations = observations
        self.confidence = confidence
        self.first_seen = first_seen or time.time()
        self.last_seen = last_seen or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trigger': self.trigger,
            'preference': self.preference,
            'observations': self.observations,
            'confidence': self.confidence,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'created_at': datetime.fromtimestamp(self.first_seen).isoformat(),
            'updated_at': datetime.fromtimestamp(self.last_seen).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Pattern':
        return cls(
            trigger=data['trigger'],
            preference=data['preference'],
            observations=data.get('observations', 0),
            confidence=data.get('confidence', 0.0),
            first_seen=data.get('first_seen', time.time()),
            last_seen=data.get('last_seen', time.time()),
        )


class PatternDetector:
    """Detecta patrones en las acciones del sistema."""

    def __init__(self):
        self._patterns: Dict[str, Pattern] = {}
        self._observations: List[Tuple[str, str]] = []  # (action, result)
        self._load_patterns()

    def record_observation(self, action: str, result: str) -> None:
        """Registra una observación: acción -> resultado."""
        self._observations.append((action, result))
        self._detect_patterns()

    def _detect_patterns(self) -> None:
        """Detecta patrones a partir de las observaciones registradas."""
        if len(self._observations) < MIN_OBSERVATIONS:
            return

        # Agrupar por (acción, resultado)
        groups: Dict[Tuple[str, str], List[int]] = {}
        for i, (action, result) in enumerate(self._observations):
            key = (action.lower(), result.lower())
            if key not in groups:
                groups[key] = []
            groups[key].append(i)

        # Detectar patrones: si una acción produce siempre el mismo resultado
        for (action, result), indices in groups.items():
            if len(indices) >= MIN_OBSERVATIONS:
                confidence = len(indices) / len(self._observations)
                if confidence >= CONFIDENCE_THRESHOLD:
                    key = f"{action}_{result}"
                    if key not in self._patterns:
                        pattern = Pattern(
                            trigger=action,
                            preference=result,
                            observations=len(indices),
                            confidence=confidence,
                            first_seen=self._observations[indices[0]][0],
                            last_seen=time.time(),
                        )
                        self._patterns[key] = pattern
                        logger.info(
                            f"Pattern detected: {action} -> {result} "
                            f"(confidence: {confidence:.2f}, observations: {len(indices)})"
                        )
                        self._save_patterns()
                        self._update_graph(pattern)

    def _update_graph(self, pattern: Pattern) -> None:
        """Actualiza el grafo cognitivo con el nuevo patrón."""
        try:
            from backend.memory.cognitive_graph_extend import get_graph_extend
            graph = get_graph_extend()
            graph.add_node(
                node_id=f"pattern:{pattern.trigger}",
                label='Pattern',
                attributes={
                    'trigger': pattern.trigger,
                    'preference': pattern.preference,
                    'confidence': pattern.confidence,
                    'observations': pattern.observations,
                    'created_at': pattern.first_seen,
                },
            )
            graph.add_edge(
                source=pattern.trigger,
                target=pattern.preference,
                relationship='PREFER',
                strength=pattern.confidence,
            )
            logger.debug(f"Graph updated with pattern: {pattern.trigger} -> {pattern.preference}")
        except Exception as e:
            logger.warning(f"Could not update graph: {e}")

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Retorna todos los patrones detectados."""
        return [p.to_dict() for p in self._patterns.values()]

    def get_pattern(self, trigger: str) -> Optional[Dict[str, Any]]:
        """Retorna un patrón específico por su trigger."""
        for key, pattern in self._patterns.items():
            if pattern.trigger == trigger:
                return pattern.to_dict()
        return None

    def _load_patterns(self) -> None:
        """Carga patrones desde archivo JSON."""
        if not PATTERNS_FILE.exists():
            return
        try:
            with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for key, pattern_data in data.items():
                self._patterns[key] = Pattern.from_dict(pattern_data)
            logger.info(f"Loaded {len(self._patterns)} patterns from {PATTERNS_FILE}")
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")

    def _save_patterns(self) -> None:
        """Guarda patrones en archivo JSON."""
        try:
            PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PATTERNS_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    {k: v.to_dict() for k, v in self._patterns.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas del detector."""
        return {
            'total_patterns': len(self._patterns),
            'total_observations': len(self._observations),
            'patterns': self.get_patterns(),
        }


# Singleton
_detector: Optional[PatternDetector] = None


def get_pattern_detector() -> PatternDetector:
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector


def reset_pattern_detector() -> None:
    global _detector
    _detector = None
