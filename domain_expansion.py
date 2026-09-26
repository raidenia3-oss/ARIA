"""AURA Domain Expansion — Jujutsu Kaisen-style particle domain system.

Gestures build energy. Releasing it triggers a domain expansion around the user.
Effects:
- Domain expansion ring + fill
- Signature-colored particle burst
- Screen distortion/glow
- Energy drain and cooldown
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from particle_engine_3d import ParticleEngine3D, Particle3D


class DomainConfig:
    def __init__(
        self,
        name: str,
        color_primary: Tuple[int, int, int],
        color_secondary: Tuple[int, int, int],
        particle_count: int = 400,
        duration: float = 4.0,
        cooldown: float = 8.0,
        energy_cost: float = 35.0,
    ) -> None:
        self.name = name
        self.color_primary = color_primary
        self.color_secondary = color_secondary
        self.particle_count = particle_count
        self.duration = duration
        self.cooldown = cooldown
        self.energy_cost = energy_cost


DOMAINS: Dict[str, DomainConfig] = {
    "open_hand": DomainConfig("Infinite Void", (30, 30, 60), (180, 180, 220), particle_count=500, duration=5.0, cooldown=10.0, energy_cost=40.0),
    "fist": DomainConfig("Cursed Energy Burst", (120, 20, 20), (255, 80, 20), particle_count=350, duration=3.5, cooldown=7.0, energy_cost=30.0),
    "peace": DomainConfig("Star Radiation", (20, 120, 40), (120, 255, 180), particle_count=420, duration=4.5, cooldown=9.0, energy_cost=38.0),
    "index": DomainConfig("Piercing Beam", (180, 140, 20), (255, 220, 90), particle_count=300, duration=3.0, cooldown=6.0, energy_cost=25.0),
    "heart": DomainConfig("Heavenly Restriction", (160, 30, 90), (255, 120, 180), particle_count=380, duration=4.0, cooldown=8.0, energy_cost=32.0),
    "swipe": DomainConfig("Black Flash", (70, 70, 90), (200, 200, 220), particle_count=460, duration=4.2, cooldown=8.5, energy_cost=36.0),
}


class DomainExpansion:
    def __init__(self, engine: ParticleEngine3D) -> None:
        self.engine = engine
        self.active: bool = False
        self.name: str = ""
        self.progress: float = 0.0
        self.energy: float = 100.0
        self.max_energy: float = 100.0
        self.regen: float = 12.0
        self.last_expansion: float = 0.0
        self.lock = threading.Lock()
        self._callbacks: List[Any] = []
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)

    def add_callback(self, cb) -> None:
        self._callbacks.append(cb)

    def _notify(self, payload: Dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                cb(payload)
            except Exception:
                pass

    def can_expand(self, gesture: str) -> bool:
        if gesture not in DOMAINS:
            return False
        if self.active:
            return False
        now = time.time()
        if now - self.last_expansion < DOMAINS[gesture].cooldown:
            return False
        return self.energy >= DOMAINS[gesture].energy_cost

    def expand(self, gesture: str, cx: float, cy: float, cz: float) -> bool:
        if not self.can_expand(gesture):
            return False
        domain = DOMAINS[gesture]
        with self.lock:
            self.active = True
            self.name = domain.name
            self.energy -= domain.energy_cost
            self.last_expansion = time.time()
            self.progress = 0.0
        self._spawn_domain(domain, cx, cy, cz)
        self._notify({
            "event": "domain_start",
            "name": domain.name,
            "gesture": gesture,
            "color_primary": domain.color_primary,
            "color_secondary": domain.color_secondary,
        })
        return True

    def _spawn_domain(self, domain: DomainConfig, cx: float, cy: float, cz: float) -> None:
        count = domain.particle_count
        ring = int(count * 0.45)
        fill = count - ring
        for _ in range(ring):
            angle = random.random() * math.pi * 2
            radius = 2.8 + random.random() * 0.25
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            z = cz + (random.random() - 0.5) * 1.6
            vx = math.cos(angle) * 0.6
            vy = math.sin(angle) * 0.6
            vz = (random.random() - 0.5) * 0.4
            life = 2.2 + random.random() * 2.4
            color = domain.color_primary if random.random() < 0.6 else domain.color_secondary
            self.engine._add_particle(Particle3D(x, y, z, vx, vy, vz, life, color, 2.0 + random.random() * 2.5))
        for _ in range(fill):
            x = cx + (random.random() - 0.5) * 5.5
            y = cy + (random.random() - 0.5) * 5.5
            z = cz + (random.random() - 0.5) * 2.8
            vx = (random.random() - 0.5) * 1.2
            vy = (random.random() - 0.5) * 1.2
            vz = (random.random() - 0.5) * 0.9
            life = 1.8 + random.random() * 2.6
            color = domain.color_secondary if random.random() < 0.55 else domain.color_primary
            self.engine._add_particle(Particle3D(x, y, z, vx, vy, vz, life, color, 1.4 + random.random() * 2.2))

    def _loop(self) -> None:
        last = time.time()
        while self._running:
            now = time.time()
            dt = min(0.05, now - last)
            last = now
            with self.lock:
                if self.active:
                    self.progress += dt / DOMAINS.get(self.name.split("::")[0] if "::" in self.name else self.name, DOMAINS["open_hand"]).duration
                    if self.progress >= 1.0:
                        self.active = False
                        self.progress = 0.0
                        self._notify({"event": "domain_end", "name": self.name})
                energy_gain = self.regen * dt
                self.energy = min(self.max_energy, self.energy + energy_gain)
            payload = {
                "event": "tick",
                "active": self.active,
                "name": self.name,
                "progress": max(0.0, min(1.0, self.progress)),
                "energy": self.energy,
                "max_energy": self.max_energy,
            }
            self._notify(payload)
            time.sleep(1 / 30)

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "active": self.active,
                "name": self.name,
                "progress": self.progress,
                "energy": self.energy,
                "max_energy": self.max_energy,
            }
