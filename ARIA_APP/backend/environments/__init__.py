# -*- coding: utf-8 -*-
"""ARIA OS - Environments Package.

Entornos especializados para diferentes áreas de trabajo:
1. Investigación - Mejoras y experimentos
2. Cerebro Global - Motor de cerebro y memoria
3. Optimización - Optimización y cosas avanzadas
4. Agentes Autónomos - Multi-tarea y despliegue autónomo
5. Innovación - Cosas imposibles y nuevas creaciones
"""

from .base import BaseEnvironment
from .research import ResearchEnvironment
from .brain import BrainEnvironment
from .optimization import OptimizationEnvironment
from .autonomous import AutonomousEnvironment
from .innovation import InnovationEnvironment

__all__ = [
    "BaseEnvironment",
    "ResearchEnvironment",
    "BrainEnvironment",
    "OptimizationEnvironment",
    "AutonomousEnvironment",
    "InnovationEnvironment",
]
