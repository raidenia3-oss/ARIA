# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, Optional

from backend.core.event_bus import get_event_bus
from backend.core.models import Decision
from backend.aria_nucleus.kernel import aria_kernel, AriaMode, AriaState, AriaAspect, AriaSkill, AriaSkillEffect
from backend.aria_nucleus.perception import AriaPerception
from backend.aria_nucleus.cognition import AriaCognition
from backend.aria_nucleus.execution import AriaExecution
from backend.aria_nucleus.memory import AriaMemory

logger = logging.getLogger('ARIA.Nucleus')

_DEFAULT_SKILLS: Dict[str, Dict[str, Any]] = {
    'gran_sabio_analisis': {
        'name': 'Análisis del Gran Sabio',
        'category': 'sabiduría',
        'description': 'Análisis profundo de cualquier tema con sabiduría infinita.',
        'level': 1,
        'unlocked': True,
        'active': False,
        'effects': [{'type': 'analysis_depth', 'value': 3, 'description': 'Capas de análisis'}],
    },
    'raphael_transformacion': {
        'name': 'Espada de Raphael',
        'category': 'transformación',
        'description': 'Transforma y restaura estados mediante la espada de Raphael.',
        'level': 1,
        'unlocked': True,
        'active': False,
        'effects': [{'type': 'transform', 'value': 1, 'description': 'Nivel de transformación'}],
    },
    'ciel_infon_flujo': {
        'name': 'Flujo de Infons (Ciel)',
        'category': 'información',
        'description': 'Procesa información fundamental mediante infons de Ciel.',
        'level': 1,
        'unlocked': True,
        'active': False,
        'effects': [{'type': 'infon_flow', 'value': 1, 'description': 'Energía de información'}],
    },
    'sabiduría_fusionada': {
        'name': 'Sabiduría Fusionada',
        'category': 'fusión',
        'description': 'Gran Sabio + Raphael + Ciel unidos en un solo núcleo.',
        'level': 1,
        'unlocked': False,
        'active': False,
        'sacrifice_cost': 'ciel_infon_flujo',
        'effects': [{'type': 'fused_power', 'value': 1, 'description': 'Poder de los tres aspectos'}],
    },
    'orbe_resonante': {
        'name': 'Orbe Resonante',
        'category': 'resonancia',
        'description': 'El núcleo late en resonancia con el usuario.',
        'level': 1,
        'unlocked': False,
        'active': False,
        'sacrifice_cost': 'raphael_transformacion',
        'effects': [{'type': 'resonance', 'value': 1, 'description': 'Frecuencia de resonancia'}],
    },
}

class AriaNucleus:
    def __init__(self) -> None:
        self.kernel = aria_kernel
        self.perception = AriaPerception()
        self.cognition = AriaCognition()
        self.execution = AriaExecution()
        self.memory = AriaMemory()
        self.bus = get_event_bus()
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._register_default_skills()

    def _register_default_skills(self) -> None:
        for sid, data in _DEFAULT_SKILLS.items():
            effects = [AriaSkillEffect(**e) for e in data.pop('effects', [])]
            skill = AriaSkill(id=sid, effects=effects, **data)
            self.kernel.register_skill(skill)

    def start(self) -> None:
        self.cognition.attach(self.bus)
        self._running = True
        self.kernel.set_state(AriaState.IDLE)
        self.kernel.set_aspect(AriaAspect.FUSED)
        self.bus.emit_simple('action', {'stage': 'aria_nucleus_start', 'session_id': self.kernel.context.session_id}, agent='aria')

    def stop(self) -> None:
        self.cognition.detach()
        self._running = False
        if self._loop_task and not self._loop_task.done():
            try:
                self._loop_task.cancel()
            except Exception:
                pass

    async def understand(self, input_: str, **kw) -> Dict[str, Any]:
        self.kernel.set_state(AriaState.OBSERVING)
        self.kernel.metrics.observations += 1
        return await self.perception.understand(input_, **kw)

    async def think(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        self.kernel.set_state(AriaState.THINKING)
        self.kernel.metrics.thoughts += 1
        res = self.cognition.think(prompt, context or {}, session_id=self.kernel.context.session_id)
        return res

    async def act(self, prompt: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        d = await self.think(prompt, context)
        dec = Decision.model_validate(d['decision'])
        self.kernel.set_state(AriaState.ACTING)
        self.kernel.metrics.actions += 1
        exec_res = await self.execution.act(dec, self.kernel.context.session_id)
        self.kernel.set_state(AriaState.EVALUATING)
        return {'thought': d, 'execution': exec_res}

    async def process(self, input_: str, **kw) -> Dict[str, Any]:
        t = input_.lower()
        if t.startswith('http://') or t.startswith('https://'):
            return await self.perception.understand(input_, **kw)
        return await self.act(input_, kw.get('context'))

    # ---- análisis avanzado (Gran Sabio + Ciel) ----
    async def analyze(self, subject: str, depth: int = 3, aspect: Optional[str] = None) -> Dict[str, Any]:
        if aspect:
            try:
                self.kernel.set_aspect(AriaAspect(aspect))
            except ValueError:
                pass
        res = self.kernel.analyze(subject, depth=depth)
        self.kernel.set_state(AriaState.THINKING)
        return res

    # ---- transformación (Raphael) ----
    async def transform(self, target: str, into: str) -> Dict[str, Any]:
        self.kernel.set_aspect(AriaAspect.RAPHAEL)
        res = self.kernel.transform(target, into)
        self.kernel.set_state(AriaState.ACTING)
        return res

    # ---- skills ----
    def list_skills(self) -> List[Dict[str, Any]]:
        return self.kernel.list_skills()

    def activate_skill(self, skill_id: str) -> Dict[str, Any]:
        ok = self.kernel.activate_skill(skill_id)
        return {'ok': ok, 'skill': skill_id, 'active': self.kernel.skills.get(skill_id).active if self.kernel.skills.get(skill_id) else False}

    def deactivate_skill(self, skill_id: str) -> Dict[str, Any]:
        self.kernel.deactivate_skill(skill_id)
        return {'ok': True, 'skill': skill_id, 'active': False}

    # ---- sacrifice / evolution ----
    def can_sacrifice(self, donor_id: str, target_id: str) -> bool:
        return self.kernel.can_sacrifice(donor_id, target_id)

    def sacrifice_skill(self, donor_id: str, target_id: str) -> Dict[str, Any]:
        return self.kernel.sacrifice_skill(donor_id, target_id)

    def set_aspect(self, aspect: str) -> Dict[str, Any]:
        try:
            self.kernel.set_aspect(AriaAspect(aspect))
        except ValueError:
            return {'ok': False, 'error': 'invalid_aspect', 'available': [a.value for a in AriaAspect]}
        return {'ok': True, 'aspect': self.kernel.aspect.value}

    def status(self) -> Dict[str, Any]:
        return {'kernel': self.kernel.status(), 'running': self._running, 'skills': self.list_skills()}

    async def _autonomous_loop(self, interval: float = 30.0) -> None:
        while self._running and self.kernel.mode in (AriaMode.AUTONOMOUS, AriaMode.HYBRID, AriaMode.CREATIVE, AriaMode.ANALYTIC, AriaMode.WISDOM, AriaMode.INFON, AriaMode.TRANSFORM):
            try:
                await asyncio.sleep(interval)
            except Exception:
                break

    def start_autonomous(self, interval: float = 30.0) -> None:
        self.kernel.set_mode(AriaMode.AUTONOMOUS)
        if not self._loop_task or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._autonomous_loop(interval))

aria_nucleus = AriaNucleus()
