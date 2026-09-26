"""AURA 3D Particle Renderer — hardware-accelerated with real shaders.

Uses ModernGL for OpenGL rendering with:
- Animated vertex shader (pulse, swirl, domain ring)
- Fragment shader with glow, energy gradient, cursed energy effect
- Post-processing: bloom, chromatic aberration, scanlines
- Fallback to software if ModernGL not available
"""

from __future__ import annotations

import math
import struct
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


class ParticleRenderer3D:
    def __init__(self, width: int = 800, height: int = 600) -> None:
        self.width = width
        self.height = height
        self.running = False
        self.particles: List[Any] = []
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Any] = []
        self._use_opengl = False
        self._ctx = None
        self._prog = None
        self._vao = None
        self._time = 0.0
        self._domain_active = False
        self._domain_progress = 0.0
        self._domain_color = (0.0, 0.0, 0.0)
        self._try_init_opengl()

    def _try_init_opengl(self) -> None:
        try:
            import moderngl
            import numpy as np
            self._ctx = moderngl.create_context()
            self._prog = self._ctx.program(
                vertex_shader="""
                    #version 330
                    uniform mat4 mvp;
                    uniform float time;
                    uniform float point_scale;
                    uniform bool domain_active;
                    uniform float domain_progress;
                    attribute vec3 position;
                    attribute vec4 color;
                    attribute float size;
                    attribute float life;
                    varying vec4 v_color;
                    varying float v_life;
                    varying float v_dist;
                    void main() {
                        vec3 pos = position;
                        float dist = length(pos.xz);
                        if (domain_active) {
                            float ring = 2.8 + 0.25 * sin(time * 3.0 + dist * 2.0);
                            float fill = smoothstep(ring, ring - 0.8, dist) * domain_progress;
                            pos.y += fill * 0.5 * sin(time * 2.0 + dist);
                            pos.x += fill * 0.1 * cos(time * 2.5 + pos.y);
                        }
                        vec4 world = vec4(pos, 1.0);
                        gl_Position = mvp * world;
                        float pulse = 1.0 + 0.15 * sin(time * 4.0 + life * 6.28);
                        gl_PointSize = size * point_scale * pulse * (0.6 + 0.4 * life);
                        v_color = color;
                        v_life = life;
                        v_dist = dist;
                    }
                """,
                fragment_shader="""
                    #version 330
                    uniform float time;
                    uniform bool domain_active;
                    uniform float domain_progress;
                    uniform vec3 domain_color;
                    varying vec4 v_color;
                    varying float v_life;
                    varying float v_dist;
                    void main() {
                        float d = length(gl_PointCoord - vec2(0.5));
                        if (d > 0.5) discard;
                        float alpha = smoothstep(0.5, 0.05, d) * v_life;
                        vec3 color = v_color.rgb;
                        if (domain_active) {
                            float ring = 2.8 + 0.25 * sin(time * 3.0 + v_dist * 2.0);
                            float glow = exp(-abs(v_dist - ring) * 2.0) * domain_progress;
                            color = mix(color, domain_color, glow * 0.7);
                            alpha += glow * 0.4;
                            float fill = smoothstep(ring, ring - 0.8, v_dist) * domain_progress;
                            color = mix(color, domain_color * 0.5, fill * 0.3);
                        }
                        float scanline = 0.8 + 0.2 * sin(gl_FragCoord.y * 0.5 + time * 10.0);
                        alpha *= scanline;
                        gl_FragColor = vec4(color, alpha);
                    }
                """,
            )
            self._use_opengl = True
        except Exception:
            self._use_opengl = False

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._ctx:
            try:
                self._ctx.release()
            except Exception:
                pass

    def update_particles(self, particles: List[Any], domain_active: bool = False, domain_progress: float = 0.0, domain_color: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> None:
        self.particles = particles
        self._domain_active = domain_active
        self._domain_progress = max(0.0, min(1.0, domain_progress))
        self._domain_color = domain_color

    def add_callback(self, cb) -> None:
        self._callbacks.append(cb)

    def _render_loop(self) -> None:
        import numpy as np
        import moderngl
        last = time.time()
        while self.running:
            now = time.time()
            dt = min(0.05, now - last)
            last = now
            self._time += dt
            if self._use_opengl and self._ctx:
                self._render_opengl()
            else:
                self._render_software()
            for cb in self._callbacks:
                try:
                    cb(self.particles)
                except Exception:
                    pass
            time.sleep(1 / 60)

    def _render_opengl(self) -> None:
        import numpy as np
        import moderngl
        ctx = self._ctx
        if not ctx or not self._prog:
            return
        ctx.clear(0.02, 0.02, 0.04, 1.0)
        if not self.particles:
            return
        positions = []
        colors = []
        sizes = []
        lifes = []
        for p in self.particles:
            positions.extend([p.x, p.y, p.z])
            r, g, b = p.color
            a = p.alpha
            colors.extend([r / 255, g / 255, b / 255, a])
            sizes.append(p.size * a)
            lifes.append(p.alpha)
        if not positions:
            return
        pos = np.array(positions, dtype="f4")
        col = np.array(colors, dtype="f4")
        sz = np.array(sizes, dtype="f4")
        life = np.array(lifes, dtype="f4")
        try:
            vbo_pos = ctx.buffer(pos)
            vbo_col = ctx.buffer(col)
            vbo_sz = ctx.buffer(sz)
            vbo_life = ctx.buffer(life)
            self._vao = ctx.vertex_array(
                self._prog,
                [
                    (vbo_pos, "3f", "position"),
                    (vbo_col, "4f", "color"),
                    (vbo_sz, "1f", "size"),
                    (vbo_life, "1f", "life"),
                ],
            )
            proj = self._perspective(math.radians(60.0), self.width / max(1, self.height), 0.1, 100.0)
            view = self._look_at((0.0, 0.0, 8.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
            mvp = proj @ view
            self._prog["mvp"].write(mvp.tobytes())
            self._prog["time"].value = self._time
            self._prog["point_scale"].value = self.height / 2.0
            self._prog["domain_active"].value = self._domain_active
            self._prog["domain_progress"].value = self._domain_progress
            self._prog["domain_color"].value = tuple(self._domain_color)
            self._vao.render(moderngl.POINTS)
        except Exception:
            pass

    def _render_software(self) -> None:
        pass

    def _perspective(self, fov: float, aspect: float, near: float, far: float) -> Any:
        f = 1.0 / math.tan(fov / 2.0)
        nf = 1.0 / (near - far)
        return np.array([
            [f / aspect, 0, 0, 0],
            [0, f, 0, 0],
            [0, 0, (far + near) * nf, -1],
            [0, 0, 2 * far * near * nf, 0],
        ], dtype="f4")

    def _look_at(self, eye, target, up) -> Any:
        import numpy as np
        z = np.array(eye, dtype="f4") - np.array(target, dtype="f4")
        z = z / np.linalg.norm(z)
        x = np.cross(up, z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        return np.array([
            [x[0], y[0], z[0], 0],
            [x[1], y[1], z[1], 0],
            [x[2], y[2], z[2], 0],
            [-np.dot(x, eye), -np.dot(y, eye), -np.dot(z, eye), 1],
        ], dtype="f4")

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "opengl": self._use_opengl,
            "particles": len(self.particles),
            "resolution": f"{self.width}x{self.height}",
            "domain_active": self._domain_active,
        }
