# Extender motor para unión real (brain+motor)
from __future__ import annotations
from typing import Dict, Any, Optional
from aria_usb.motor.core import ModelConfig
from aria_usb.motor.manager import ModelManager
from aria_usb.motor.router import HybridRouter
from aria_usb.motor.modules import ModuleRegistry

class Brain:
    def __init__(self, mgr: ModelManager):
        self.mgr = mgr
    def think(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.mgr.load_unified()
        return {"thought": "unified", "model": self.mgr.active}

class Motor:
    def __init__(self, mgr: ModelManager):
        self.mgr = mgr
    def act(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        self.mgr.load_unified()
        return {"action": "execute", "model": self.mgr.active}

class BrainMotor:
    def __init__(self):
        self.cfg = ModelConfig()
        self.mgr = ModelManager(self.cfg)
        self.router = HybridRouter(self.mgr, self.cfg)
        self.reg = ModuleRegistry(self.cfg)
        self.brain = Brain(self.mgr)
        self.motor = Motor(self.mgr)
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        r = self.router.route(input_data)
        t = self.brain.think(input_data)
        a = self.motor.act(t)
        return {"route": r, "thought": t, "action": a, "active": self.mgr.active}
