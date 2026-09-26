# Inicialización del módulo de memoria de AURA OS
# -*- coding: utf-8 -*-
"""Chunk 3: Memory package.

Contiene:
  - MemoryManager         (tiered memory: short/medium/long)
  - PatternDetector       (reglas de patrones: cuando X prefiere Y)
  - CognitiveGraphExtend  (extiende el grafo cognitivo en tiempo real)
"""
from .manager import MemoryManager, get_memory_manager, reset_memory_manager
from .pattern_detector import PatternDetector, get_pattern_detector, reset_pattern_detector
from .cognitive_graph_extend import CognitiveGraphExtend, get_graph_extend, reset_graph_extend

__all__ = [
    "MemoryManager",
    "PatternDetector",
    "CognitiveGraphExtend",
    "get_memory_manager",
    "get_pattern_detector",
    "get_graph_extend",
    "reset_memory_manager",
    "reset_pattern_detector",
    "reset_graph_extend",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
