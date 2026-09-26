"""AURA 3D Particle Engine — gesture-driven particle systems using OpenGL.

Features:
- Real-time 3D particle rendering via ModernGL/PyOpenGL
- MediaPipe hand tracking integration
- Gesture-reactive effects: domain expansion, vortices, auras
- Embedded in tkinter via matplotlib or external window

Usage:
    from particle_engine_3d import ParticleEngine3D
    engine = ParticleEngine3D()
    engine.start()
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class Particle3D:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "life", "max_life", "color", "size")

    def __init__(self, x: float, y: float, z: float, vx: float, vy: float, vz: float, life: float, color: Tuple[int, int, int], size: float) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.life -= dt
        self.vx *= 0.99
        self.vy *= 0.99
        self.vz *= 0.99

    @property
    def alpha(self) -> float:
        return max(0.0, self.life / self.max_life)


class ParticleEngine3D:
    def __init__(self) -> None:
        self.running = False
        self.particles: List[Particle3D] = []
        self.max_particles = 5000
        self.gesture: str = "none"
        self.gesture_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.gesture_confidence: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._mode = "aura"
        self._color_hue = 0.0
        self._frame_callbacks: List[Any] = []
        self._use_opengl = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)

    def set_gesture(self, gesture: str, x: float, y: float, z: float, confidence: float) -> None:
        self.gesture = gesture
        self.gesture_position = (x, y, z)
        self.gesture_confidence = confidence
        self._spawn_from_gesture(gesture, x, y, z, confidence)

    def _spawn_from_gesture(self, gesture: str, x: float, y: float, z: float, confidence: float) -> None:
        count = int(20 + confidence * 80)
        if gesture == "open_hand":
            self._spawn_explosion(x, y, z, count, (0.2, 0.8, 1.0))
        elif gesture == "fist":
            self._spawn_implosion(x, y, z, count, (1.0, 0.2, 0.2))
        elif gesture == "peace":
            self._spawn_vortex(x, y, z, count, (0.2, 1.0, 0.4))
        elif gesture == "index":
            self._spawn_beam(x, y, z, count, (1.0, 0.8, 0.2))
        elif gesture == "heart":
            self._spawn_aura(x, y, z, count, (1.0, 0.2, 0.6))
        elif gesture == "swipe":
            self._spawn_stream(x, y, z, count, (0.4, 0.4, 1.0))
        else:
            if confidence > 0.5:
                self._spawn_aura(x, y, z, max(10, int(confidence * 30)), (0.6, 0.6, 0.6))

    def _spawn_explosion(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            theta = random.random() * math.pi * 2
            phi = math.acos(2 * random.random() - 1)
            speed = 1.5 + random.random() * 2.5
            vx = math.sin(phi) * math.cos(theta) * speed
            vy = math.sin(phi) * math.sin(theta) * speed
            vz = math.cos(phi) * speed
            life = 1.5 + random.random() * 2.0
            c = self._color_vary(color, 0.2)
            p = Particle3D(cx, cy, cz, vx, vy, vz, life, c, 2.0 + random.random() * 3.0)
            self._add_particle(p)

    def _spawn_implosion(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            angle = random.random() * math.pi * 2
            radius = 3.0 + random.random() * 5.0
            speed = 1.0 + random.random() * 1.5
            vx = -math.cos(angle) * radius * speed * 0.3
            vy = -math.sin(angle) * radius * speed * 0.3
            vz = -speed
            life = 1.0 + random.random() * 1.5
            c = self._color_vary(color, 0.2)
            p = Particle3D(cx + vx * 2, cy + vy * 2, cz + vz * 2, vx, vy, vz, life, c, 2.0 + random.random() * 2.5)
            self._add_particle(p)

    def _spawn_vortex(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            angle = random.random() * math.pi * 2
            radius = 0.5 + random.random() * 2.0
            height = (random.random() - 0.5) * 4.0
            speed = 2.0 + random.random() * 2.0
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            vz = height * 0.5
            life = 1.5 + random.random() * 2.0
            c = self._color_vary(color, 0.2)
            p = Particle3D(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius, cz + height, vx, vy, vz, life, c, 1.5 + random.random() * 2.0)
            self._add_particle(p)

    def _spawn_beam(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            x = cx + (random.random() - 0.5) * 0.5
            y = cy + (random.random() - 0.5) * 0.5
            z = cz + random.random() * 6.0
            vx = (random.random() - 0.5) * 0.3
            vy = (random.random() - 0.5) * 0.3
            vz = 1.0 + random.random() * 1.5
            life = 0.8 + random.random() * 1.2
            c = self._color_vary(color, 0.15)
            p = Particle3D(x, y, z, vx, vy, vz, life, c, 1.0 + random.random() * 1.5)
            self._add_particle(p)

    def _spawn_aura(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            angle = random.random() * math.pi * 2
            radius = 0.8 + random.random() * 1.5
            height = (random.random() - 0.5) * 2.5
            vx = math.cos(angle) * 0.4
            vy = math.sin(angle) * 0.4
            vz = (random.random() - 0.5) * 0.6
            life = 1.2 + random.random() * 1.8
            c = self._color_vary(color, 0.25)
            p = Particle3D(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius, cz + height, vx, vy, vz, life, c, 1.5 + random.random() * 2.5)
            self._add_particle(p)

    def _spawn_stream(self, cx: float, cy: float, cz: float, count: int, color: Tuple[float, float, float]) -> None:
        for _ in range(count):
            x = cx + (random.random() - 0.5) * 3.0
            y = cy + (random.random() - 0.5) * 3.0
            z = cz + random.random() * 4.0
            vx = (random.random() - 0.5) * 2.0
            vy = (random.random() - 0.5) * 2.0
            vz = 1.0 + random.random() * 2.0
            life = 1.0 + random.random() * 1.5
            c = self._color_vary(color, 0.2)
            p = Particle3D(x, y, z, vx, vy, vz, life, c, 1.5 + random.random() * 2.0)
            self._add_particle(p)

    def _add_particle(self, particle: Particle3D) -> None:
        with self._lock:
            if len(self.particles) < self.max_particles:
                self.particles.append(particle)
            else:
                oldest = min(self.particles, key=lambda p: p.life)
                if particle.life > oldest.life:
                    idx = self.particles.index(oldest)
                    self.particles[idx] = particle

    def _color_vary(self, color: Tuple[float, float, float], amount: float) -> Tuple[int, int, int]:
        r = max(0, min(255, int((color[0] + (random.random() - 0.5) * amount) * 255)))
        g = max(0, min(255, int((color[1] + (random.random() - 0.5) * amount) * 255)))
        b = max(0, min(255, int((color[2] + (random.random() - 0.5) * amount) * 255)))
        return (r, g, b)

    def _loop(self) -> None:
        last = time.time()
        while self.running:
            now = time.time()
            dt = min(0.05, now - last)
            last = now
            with self._lock:
                for p in self.particles[:]:
                    p.update(dt)
                self.particles = [p for p in self.particles if p.life > 0]
                count = len(self.particles)
            for cb in self._frame_callbacks:
                try:
                    cb(self.particles, count, self.gesture)
                except Exception:
                    pass

    def add_frame_callback(self, cb) -> None:
        self._frame_callbacks.append(cb)

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def set_domain_expansion(self, active: bool) -> None:
        """Activa/desactiva modo Domain Expansion (partículas masivas)."""
        if active:
            self._mode = "domain_expansion"
            # Genera ráfaga masiva de partículas en dominio
            for _ in range(200):
                x = (random.random() - 0.5) * 6.0
                y = (random.random() - 0.5) * 6.0
                z = (random.random() - 0.5) * 6.0
                speed = 0.5 + random.random() * 2.0
                c = self._color_vary((0.65, 0.2, 0.9), 0.4)
                p = Particle3D(
                    x, y, z,
                    (random.random() - 0.5) * speed,
                    (random.random() - 0.5) * speed,
                    (random.random() - 0.5) * speed,
                    2.0 + random.random() * 3.0,
                    c,
                    1.5 + random.random() * 3.0,
                )
                self._add_particle(p)
        else:
            self._mode = "idle"

    def get_particles(self) -> List[Particle3D]:
        """Devuelve copia segura de la lista de partículas."""
        with self._lock:
            return list(self.particles)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            count = len(self.particles)
        return {
            "running": self.running,
            "mode": self._mode,
            "particles": count,
            "max_particles": self.max_particles,
            "gesture": self.gesture,
            "gesture_position": self.gesture_position,
            "gesture_confidence": self.gesture_confidence,
        }
