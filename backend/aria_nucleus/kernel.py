# -*- coding: utf-8 -*-
"""ARIA Kernel - Núcleo del personaje ARIA (Gran Sabio + Raphael + Ciel)"""
from __future__ import annotations
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger('ARIA.Kernel')

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

class AriaMode(str, Enum):
    REACTIVE = 'reactive'
    AUTONOMOUS = 'autonomous'
    HYBRID = 'hybrid'
    CREATIVE = 'creative'
    ANALYTIC = 'analytic'
    WISDOM = 'wisdom'      # Gran Sabio - análisis profundo y sabiduría
    TRANSFORM = 'transform'# Raphael - transformación y restauración
    INFON = 'infon'        # Ciel - procesamiento de información fundamental

class AriaState(str, Enum):
    IDLE = 'idle'
    OBSERVING = 'observing'
    THINKING = 'thinking'
    ACTING = 'acting'
    EVALUATING = 'evaluating'
    PAUSED = 'paused'
    ERROR = 'error'
    RESONATING = 'resonating'
    SACRIFICING = 'sacrificing'
    EVOLVING = 'evolving'

class AriaAspect(str, Enum):
    GRAN_SABIO = 'gran_sabio'     # sabiduría, análisis, observación
    RAPHAEL = 'raphael'           # transformación, restauración, espada
    CIEL = 'ciel'                 # información, infons, energía fundamental
    FUSED = 'fused'               # los tres unidos

@dataclass
class AriaSkillEffect:
    type: str
    value: Any
    description: str = ''

@dataclass
class AriaSkill:
    id: str
    name: str
    category: str
    level: int = 1
    description: str = ''
    cost: Dict[str, Any] = field(default_factory=dict)
    effects: List[AriaSkillEffect] = field(default_factory=list)
    evolved_from: Optional[str] = None
    evolves_to: Optional[str] = None
    sacrifice_target: Optional[str] = None  # skill id que esta skill puede sacrificar para evolucionar
    unlocked: bool = False
    active: bool = False
    sacrifice_cost: Optional[str] = None    # id de skill requerida como sacrificio para desbloquear

@dataclass
class AriaContext:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: Optional[str] = None
    focus: Optional[str] = None
    environment: Dict[str, Any] = field(default_factory=dict)
    active_task: Optional[str] = None
    last_observation: Optional[Dict[str, Any]] = None
    last_action: Optional[Dict[str, Any]] = None
    memory_context: Dict[str, Any] = field(default_factory=dict)
    perception_context: Dict[str, Any] = field(default_factory=dict)
    aspect: AriaAspect = AriaAspect.FUSED

@dataclass
class AriaMetrics:
    thoughts: int = 0
    actions: int = 0
    observations: int = 0
    errors: int = 0
    sacrifices: int = 0
    evolutions: int = 0
    analyses: int = 0
    uptime_start: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    @property
    def uptime_s(self) -> float:
        return time.time() - self.uptime_start

class AriaKernel:
    def __init__(self) -> None:
        self.identity = 'ARIA'
        self.description = 'Ambient Runtime Intelligence Assistant - Gran Sabio / Raphael / Ciel Core'
        self.mode = AriaMode.HYBRID
        self.state = AriaState.IDLE
        self.aspect = AriaAspect.FUSED
        self.context = AriaContext()
        self.metrics = AriaMetrics()
        self.skills: Dict[str, AriaSkill] = {}
        self.sacrifice_log: List[Dict[str, Any]] = []

    # ---- modos / aspectos ----
    def set_mode(self, mode: AriaMode) -> None:
        self.mode = mode

    def set_state(self, state: AriaState) -> None:
        self.state = state
        self.metrics.last_heartbeat = time.time()

    def set_aspect(self, aspect: AriaAspect) -> None:
        self.aspect = aspect

    # ---- skills ----
    def register_skill(self, skill: AriaSkill) -> None:
        self.skills[skill.id] = skill

    def get_skill(self, skill_id: str) -> Optional[AriaSkill]:
        return self.skills.get(skill_id)

    def list_skills(self) -> List[Dict[str, Any]]:
        return [{
            'id': s.id, 'name': s.name, 'category': s.category, 'level': s.level,
            'description': s.description, 'unlocked': s.unlocked, 'active': s.active,
            'evolved_from': s.evolved_from, 'evolves_to': s.evolves_to,
            'sacrifice_cost': s.sacrifice_cost, 'sacrifice_target': s.sacrifice_target,
        } for s in self.skills.values()]

    def activate_skill(self, skill_id: str) -> bool:
        s = self.skills.get(skill_id)
        if not s or not s.unlocked:
            return False
        for sk in self.skills.values():
            sk.active = False
        s.active = True
        self.set_state(AriaState.ACTING)
        return True

    def deactivate_skill(self, skill_id: str) -> None:
        s = self.skills.get(skill_id)
        if s:
            s.active = False
        self.set_state(AriaState.IDLE)

    # ---- sacrifice / evolution ----
    def can_sacrifice(self, donor_id: str, target_id: str) -> bool:
        donor = self.skills.get(donor_id)
        target = self.skills.get(target_id)
        if not donor or not target:
            return False
        if not donor.unlocked or donor.active:
            return False
        if target.sacrifice_cost and target.sacrifice_cost != donor_id:
            return False
        return True

    def sacrifice_skill(self, donor_id: str, target_id: str) -> Dict[str, Any]:
        donor = self.skills.get(donor_id)
        target = self.skills.get(target_id)
        if not donor or not target:
            return {'ok': False, 'error': 'skill_not_found'}
        if not self.can_sacrifice(donor_id, target_id):
            return {'ok': False, 'error': 'cannot_sacrifice'}

        donor.unlocked = False
        donor.active = False
        target.unlocked = True
        target.level = (target.level or 0) + 1
        self.metrics.sacrifices += 1
        self.metrics.evolutions += 1
        self.set_state(AriaState.EVOLVING)

        record = {
            'ts': _now_iso(),
            'donor': donor_id,
            'donor_name': donor.name,
            'target': target_id,
            'target_name': target.name,
            'new_level': target.level,
        }
        self.sacrifice_log.append(record)
        logger.info('[ARIA] sacrifice %s -> %s (nivel %s)', donor_id, target_id, target.level)
        return {'ok': True, 'sacrificed': donor_id, 'evolved': target_id, 'record': record}

    # ---- analysis (Gran Sabio + Ciel) ----
    def analyze(self, subject: str, depth: int = 3) -> Dict[str, Any]:
        self.metrics.analyses += 1
        self.set_state(AriaState.THINKING)
        return {
            'subject': subject,
            'depth': depth,
            'aspect': self.aspect.value,
            'insights': [
                f'[{self.aspect.value}] Estructura de "{subject}" mapeada en {depth} capas.',
                f'[{AriaAspect.GRAN_SABIO.value}] Patrón recurrente detectado: conocimiento cíclico.',
                f'[{AriaAspect.CIEL.value}] Infons fluyen: {subject} emite señales de información fundamental.',
                f'[{AriaAspect.RAPHAEL.value}] Punto de transformación identificado: "{subject}" puede ser reconfigurado.',
            ],
            'confidence': 0.92,
            'ts': _now_iso(),
        }

    def transform(self, target: str, into: str) -> Dict[str, Any]:
        """Raphael: transformación y restauración de estado."""
        self.set_state(AriaState.TRANSFORM if hasattr(AriaState, 'TRANSFORM') else AriaState.ACTING)
        return {
            'from': target,
            'into': into,
            'aspect': AriaAspect.RAPHAEL.value,
            'result': f'{target} transformado en {into} mediante espada de Raphael.',
            'ts': _now_iso(),
        }

    def heartbeat(self) -> Dict[str, Any]:
        self.metrics.last_heartbeat = time.time()
        return {
            'identity': self.identity,
            'mode': self.mode.value,
            'state': self.state.value,
            'aspect': self.aspect.value,
            'uptime_s': round(self.metrics.uptime_s, 2),
            'thoughts': self.metrics.thoughts,
            'actions': self.metrics.actions,
            'observations': self.metrics.observations,
            'errors': self.metrics.errors,
            'sacrifices': self.metrics.sacrifices,
            'evolutions': self.metrics.evolutions,
            'analyses': self.metrics.analyses,
            'session_id': self.context.session_id,
            'ts': _now_iso(),
        }

    def status(self) -> Dict[str, Any]:
        return self.heartbeat()

aria_kernel = AriaKernel()
