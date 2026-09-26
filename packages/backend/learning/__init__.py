# -*- coding: utf-8 -*-
"""AURA OS — Learning Modules Package."""
from __future__ import annotations

from backend.learning.auto_documentation import AutoDocumenter, auto_documenter
from backend.learning.learning_loop import LearningEngine, learning_engine
from backend.learning.mistake_memory import MistakeMemory, mistake_memory
from backend.learning.knowledge_graph import KnowledgeGraph, knowledge_graph
from backend.learning.auto_prompt import AutoPromptGenerator, auto_prompt_generator
from backend.learning.auto_scaling import AutoScaler, auto_scaler

__all__ = [
    "AutoDocumenter", "auto_documenter",
    "LearningEngine", "learning_engine",
    "MistakeMemory", "mistake_memory",
    "KnowledgeGraph", "knowledge_graph",
    "AutoPromptGenerator", "auto_prompt_generator",
    "AutoScaler", "auto_scaler",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
