#!/usr/bin/env python3
"""
AURA — Autonomous AI Ecosystem Desktop App
Standalone desktop application with integrated chat, control panel, logs,
training management, and full system orchestration. No browser required.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from agent_bridge import AgentBridge, AutoFixer
except Exception:
    AgentBridge = None
    AutoFixer = None

try:
    from mobile_prep import MobilePrep
except Exception:
    MobilePrep = None

try:
    from aura_brain import AuraBrain, AuraBrainAPI
except Exception:
    AuraBrain = None
    AuraBrainAPI = None

try:
    from brain_orchestrator import BrainOrchestrator
except Exception:
    BrainOrchestrator = None

try:
    from backend_embedded import EmbeddedAuraBackend
except Exception:
    EmbeddedAuraBackend = None

try:
    from voice_engine import VoiceEngine
except Exception:
    VoiceEngine = None

try:
    from gesture_engine import GestureEngine
except Exception:
    GestureEngine = None

try:
    from vision_roi import VisionROI
except Exception:
    VisionROI = None

try:
    from osint_dashboard import OSINTDashboard
except Exception:
    OSINTDashboard = None

try:
    from ai_providers import AIProviderManager
except Exception:
    AIProviderManager = None

try:
    from aura_plugin_system import PluginManager
except Exception:
    PluginManager = None


ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Theme / constants — NUCLEOS v3 Modern Dark Glass
# ---------------------------------------------------------------------------
BG = "#05070a"
BG2 = "#080c12"
PANEL = "#0d1117"
PANEL2 = "#111820"
ACCENT = "#7c4dff"
ACCENT2 = "#00e5ff"
ACCENT3 = "#f72585"
TEXT = "#e6e9f0"
TEXT2 = "#a8b2c1"
TEXT_DIM = "#5c6478"
RED = "#ff4d4d"
GREEN = "#00e676"
YELLOW = "#ffea00"
BLUE = "#38bdf8"
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_H2 = ("Segoe UI", 13, "bold")
FONT_H3 = ("Segoe UI", 11, "bold")
FONT_MONO = ("Consolas", 9)
FONT_JJK = ("Impact", 24, "bold")
FONT_JJK_SMALL = ("Impact", 14, "bold")

SYSTEM_PROMPT = "Eres AURA, asistente avanzado."  # prompt base compartido chat/stream


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"


def _blend(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))


def _glow(color, intensity=0.4):
    r, g, b = _hex_to_rgb(color)
    darken = 1 - intensity
    return _rgb_to_hex(int(r*darken), int(g*darken), int(b*darken))


GLASS_BG = "rgba(13,17,23,0.85)"
GLASS_BORDER = "rgba(124,77,255,0.15)"
GLASS_BORDER_HOVER = "rgba(0,229,255,0.3)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run(cmd: list[str], cwd: Optional[Path] = None, capture: bool = True) -> tuple[int, str, str]:
    cwd = cwd or ROOT
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=capture,
            text=True,
            shell=platform.system() == "Windows" and len(cmd) == 1,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except Exception as exc:
        return 1, "", str(exc)


def ensure_deps() -> None:
    req = ROOT / "requirements.txt"
    if not req.exists():
        return
    run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools", "wheel"])
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])


# ---------------------------------------------------------------------------
# Backend client
# ---------------------------------------------------------------------------
class AuraClient:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = os.getenv("AURA_API_KEY", "")
        self._headers = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["X-API-Key"] = self.api_key

    def health(self) -> Dict[str, Any]:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=3) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    def chat(self, message: str, history: Optional[List[List[str]]] = None) -> Dict[str, Any]:
        payload = {
            "message": message,
            "history": history or [],
            "system_prompt": SYSTEM_PROMPT,
            "temperature": 0.7,
            "max_tokens": 512,
        }
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/hf-chat",
                data=data,
                headers={**self._headers, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"error": str(exc)}

    def status(self) -> Dict[str, Any]:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/status",
                headers=self._headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"error": str(exc)}

    def logs(self, service: str = "backend", lines: int = 100) -> Dict[str, Any]:
        try:
            import urllib.request
            url = f"{self.base_url}/api/logs?service={service}&lines={lines}"
            req = urllib.request.Request(url, headers=self._headers, method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"error": str(exc)}

    def chat_stream(self, message: str, history: Optional[List[List[str]]] = None, system_prompt: str = "", on_token=None) -> None:
        """Streaming SSE desde /api/chat/stream; dispara on_token(piece) por chunk."""
        import urllib.request as _url
        payload = json.dumps({"message": message, "history": history or [], "system_prompt": system_prompt}).encode()
        req = _url.Request(
            f"{self.base_url}/api/chat/stream",
            data=payload, headers={**self._headers, "Content-Type": "application/json"}, method="POST",
        )
        with _url.urlopen(req, timeout=300) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                pkt = line[5:].strip()
                if pkt == "[DONE]":
                    return
                try:
                    obj = json.loads(pkt)
                except Exception:
                    continue
                if "error" in obj:
                    raise RuntimeError(obj["error"])
                piece = obj.get("token", "")
                if piece and on_token:
                    on_token(piece)

    def ollama_status(self) -> Dict[str, Any]:
        try:
            import urllib.request as _url
            with _url.urlopen(f"{self.base_url}/api/ai/ollama", timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"online": False, "error": str(exc)}


    def training_status(self) -> Dict[str, Any]:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/api/training/status",
                headers=self._headers,
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"error": str(exc)}

    def start_training(self, model_name: str, dataset_path: str, output_dir: str) -> Dict[str, Any]:
        payload = {
            "model_name": model_name,
            "dataset_path": dataset_path,
            "output_dir": output_dir,
        }
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.base_url}/api/training/start",
                data=data,
                headers={**self._headers, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Log queue for background worker
# ---------------------------------------------------------------------------
class LogStreamer(threading.Thread):
    def __init__(self, log_queue: queue.Queue) -> None:
        super().__init__(daemon=True)
        self.log_queue = log_queue
        self._running = True

    def run(self) -> None:
        tail_proc: Optional[subprocess.Popen] = None
        try:
            log_path = ROOT / "backend" / "uvicorn.log"
            if platform.system() == "Windows":
                tail_proc = subprocess.Popen(
                    ["powershell", "-Command", f"Get-Content '{log_path}' -Wait -Tail 50"],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            else:
                tail_proc = subprocess.Popen(
                    ["tail", "-f", "-n", "50", str(log_path)],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            while self._running:
                line = tail_proc.stdout.readline()
                if not line:
                    break
                self.log_queue.put(("log", line.rstrip()))
        except Exception:
            pass
        finally:
            if tail_proc:
                try:
                    tail_proc.kill()
                except Exception:
                    pass

    def stop(self) -> None:
        self._running = False


# ---------------------------------------------------------------------------
# Nucleus Canvas — Animated Core Visualization
# ---------------------------------------------------------------------------
class NucleusCanvas:
    """Animated rotating core/nucleus visualization for the header."""

    def __init__(self, parent, width=200, height=80) -> None:
        self.canvas = tk.Canvas(
            parent, width=width, height=height,
            bg=BG, highlightthickness=0,
        )
        self.w = width
        self.h = height
        self._t = 0.0
        self._running = True
        self._status = "active"
        self._orb_items = []
        self._particle_items = []
        self._particle_trails: List[List[tuple]] = []
        self._trail_items: List[int] = []
        self._core_id = None
        self._glow_id = None
        self._text_id = None
        self._scan_id = None
        self._scan2_id = None
        self._inner_glow_id = None
        self._status_colors = {
            "active": (ACCENT, ACCENT2),
            "warning": (YELLOW, "#fbbf24"),
            "error": (RED, "#ef4444"),
            "listening": ("#22d3ee", "#06b6d4"),
            "thinking": ("#f59e0b", "#d97706"),
            "speaking": ("#f472b6", "#ec4899"),
            "processing": ("#a78bfa", "#8b5cf6"),
            "ready": (ACCENT, ACCENT2),
        }
        # Per-state animation config: breathing speed/amplitude/radii.
        self._state_anim = {
            "listening": {"speed": 2.2, "amp": 0.22, "glow_amp": 0.30, "breath_max": 1.6},
            "thinking": {"speed": 0.9, "amp": 0.12, "glow_amp": 0.18, "breath_max": 1.2},
            "speaking": {"speed": 3.2, "amp": 0.30, "glow_amp": 0.35, "breath_max": 1.8},
            "processing": {"speed": 1.6, "amp": 0.18, "glow_amp": 0.25, "breath_max": 1.4},
            "active": {"speed": 1.5, "amp": 0.15, "glow_amp": 0.20, "breath_max": 1.25},
            "ready": {"speed": 1.2, "amp": 0.10, "glow_amp": 0.15, "breath_max": 1.15},
            "warning": {"speed": 0.8, "amp": 0.08, "glow_amp": 0.12, "breath_max": 1.1},
            "error": {"speed": 0.6, "amp": 0.06, "glow_amp": 0.10, "breath_max": 1.05},
        }
        self._anim_speed = 1.5
        self._anim_amp = 0.15
        self._glow_amp = 0.20
        self._breath_max = 1.25
        self._breath_phase = 0.0
        self._breath_id = None
        self._react_pulse = 0.0  # reaction impulse on orbReact() (0..1, decays)
        self._target_colors: Optional[tuple] = None
        self._current_colors: tuple = (ACCENT, ACCENT2)
        self._draw_nucleus()

    def _draw_nucleus(self) -> None:
        cx, cy = self.w // 2, self.h // 2
        # Outer glow (simulated gradient with 3 overlapping circles)
        self._glow_id = self.canvas.create_oval(
            cx - 35, cy - 35, cx + 35, cy + 35,
            fill=_glow(ACCENT, 0.08), outline="",
        )
        self.canvas.create_oval(
            cx - 28, cy - 28, cx + 28, cy + 28,
            fill=_glow(ACCENT, 0.12), outline="",
        )
        self.canvas.create_oval(
            cx - 22, cy - 22, cx + 22, cy + 22,
            fill=_glow(ACCENT, 0.18), outline="",
        )
        # Breathing halo (expands/contracts with state)
        self._breath_id = self.canvas.create_oval(
            cx - 40, cy - 40, cx + 40, cy + 40,
            outline=_glow(ACCENT2, 0.25), width=1,
        )
        # Core orb
        self._core_id = self.canvas.create_oval(
            cx - 14, cy - 14, cx + 14, cy + 14,
            fill=ACCENT, outline=ACCENT2, width=2,
        )
        # Inner highlight
        self.canvas.create_oval(
            cx - 6, cy - 8, cx + 2, cy,
            fill="#FFFFFF", outline="",
        )
        # Inner glow hotspot
        self._inner_glow_id = self.canvas.create_oval(
            cx - 8, cy - 8, cx + 8, cy + 8,
            fill=_glow(ACCENT, 0.25), outline="",
        )
        # Label
        self._text_id = self.canvas.create_text(
            cx, cy + 30, text="AURA NÚCLEO",
            fill=TEXT2, font=("Segoe UI", 7, "bold"),
        )
        # Particles (16, matching web frontend) with trails
        for i in range(16):
            angle = (i / 16) * 2 * 3.14159
            x = cx + int(45 * math.cos(angle))
            y = cy + int(20 * math.sin(angle))
            item = self.canvas.create_oval(x - 2, y - 2, x + 2, y + 2,
                                           fill=ACCENT2, outline="")
            self._particle_items.append((item, angle, 45, 20))
            self._particle_trails.append([])
            self._trail_items.append([])
        # Orbital rings
        self.canvas.create_oval(
            cx - 45, cy - 20, cx + 45, cy + 20,
            outline="#1a1540", width=1,
        )
        self.canvas.create_oval(
            cx - 55, cy - 28, cx + 55, cy + 28,
            outline="#0a2030", width=1,
        )
        # Scan arc (rotating light beam effect)
        self._scan_id = self.canvas.create_arc(
            cx - 50, cy - 50, cx + 50, cy + 50,
            start=0, extent=30, fill=_glow(ACCENT, 0.06),
            outline="", style="pieslice",
        )
        self._scan2_id = self.canvas.create_arc(
            cx - 45, cy - 45, cx + 45, cy + 45,
            start=180, extent=20, fill=_glow(ACCENT2, 0.04),
            outline="", style="pieslice",
        )
        self._animate()

    def _animate(self) -> None:
        if not self._running:
            return
        self._t += 0.04
        cx, cy = self.w // 2, self.h // 2

        # Smooth color transition
        if self._target_colors:
            c1_cur = self._current_colors[0]
            c2_cur = self._current_colors[1]
            c1_tgt = self._target_colors[0]
            c2_tgt = self._target_colors[1]
            # Simple interpolation by mixing toward target
            self._current_colors = (
                _blend(c1_cur, c1_tgt, 0.08),
                _blend(c2_cur, c2_tgt, 0.08),
            )
            self.canvas.itemconfig(self._core_id, fill=self._current_colors[0])
            self.canvas.itemconfig(self._inner_glow_id, fill=_glow(self._current_colors[0], 0.25))

        # Pulse core (+reaction impulse)
        if self._react_pulse > 0:
            self._react_pulse = max(0.0, self._react_pulse - 0.06)
        speed = self._anim_speed
        pulse = 1 + self._anim_amp * math.sin(self._t * 3 * speed / 1.5) + self._react_pulse * 0.25
        r = max(6, int(14 * pulse))
        self.canvas.coords(self._core_id, cx - r, cy - r, cx + r, cy + r)

        # Glow pulse (expanding)
        glow_r = int(35 * (1 + self._glow_amp * math.sin(self._t * 2 * speed / 1.5 + self._react_pulse)))
        self.canvas.coords(self._glow_id, cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r)

        # Inner glow pulse
        ig_r = max(3, int(8 * (1 + 0.2 * math.sin(self._t * 2.5 * speed / 1.5) + self._react_pulse * 0.3)))
        self.canvas.coords(self._inner_glow_id, cx - ig_r, cy - ig_r, cx + ig_r, cy + ig_r)

        # Breathing halo (expands/contracts with slow phase + state max)
        if self._breath_id is not None:
            self._breath_phase += 0.03 * speed / 1.5
            br = (1 + math.sin(self._breath_phase)) / 2  # 0..1
            hr = int(40 * (1.0 + (self._breath_max - 1.0) * br) + self._react_pulse * 8)
            try:
                self.canvas.coords(self._breath_id, cx - hr, cy - hr, cx + hr, cy + hr)
                self.canvas.itemconfig(self._breath_id, outline=_glow(self._current_colors[1], 0.25))
            except Exception:
                pass

        # Rotate scan arcs
        self.canvas.itemconfig(self._scan_id, start=self._t * 60)
        self.canvas.itemconfig(self._scan2_id, start=self._t * 45 + 180)

        # Rotate particles with trails
        for i, (item, base_angle, orbit_r, orbit_y) in enumerate(self._particle_items):
            angle = base_angle + self._t * (0.8 + i * 0.05)
            x = cx + int(orbit_r * math.cos(angle))
            y = cy + int(orbit_y * math.sin(angle))
            self.canvas.coords(item, x - 2, y - 2, x + 2, y + 2)

            # Trail
            trail = self._particle_trails[i]
            trail.append((x, y))
            if len(trail) > 6:
                trail.pop(0)

            # Update trail items
            trail_items = self._trail_items[i]
            # Remove old trail items
            for ti in trail_items:
                try:
                    self.canvas.delete(ti)
                except Exception:
                    pass
            trail_items.clear()

            for j, (tx, ty) in enumerate(trail):
                opacity = (j + 1) / len(trail)
                size = max(1, int(2 * opacity))
                ti = self.canvas.create_oval(
                    tx - size, ty - size, tx + size, ty + size,
                    fill=_glow(ACCENT2, opacity * 0.3), outline=""
                )
                trail_items.append(ti)

        # Color shift based on status
        if self._status in self._status_colors:
            self._target_colors = self._status_colors[self._status]

        self.canvas.after(50, self._animate)

    def set_status(self, status: str) -> None:
        self._status = status
        cfg = self._state_anim.get(status)
        if cfg:
            self._anim_speed = cfg["speed"]
            self._anim_amp = cfg["amp"]
            self._glow_amp = cfg["glow_amp"]
            self._breath_max = cfg["breath_max"]

    def react(self) -> None:
        """Impulso visual (flash) ante un evento: envío, respuesta, voz."""
        self._react_pulse = 1.0

    def on_token(self, piece: str = "") -> None:
        """Reacción impulsada por cada chunk recibido del stream Ollama/TTS."""
        self._react_pulse = max(self._react_pulse, 0.45)
        if self._status != "speaking":
            self.set_status("speaking")

    def status_color(self) -> tuple:
        return tuple(self._current_colors)

    @property
    def status(self) -> str:
        return self._status

    def destroy(self) -> None:
        self._running = False

    def widget(self) -> tk.Canvas:
        return self.canvas


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------
class AuraApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AURA OS — Núcleo v3")
        self.root.geometry("1400x900")
        self.root.minsize(1100, 700)
        self.root.configure(bg=BG)

        self.client = AuraClient()
        self.embedded = EmbeddedAuraBackend(str(ROOT)) if EmbeddedAuraBackend else None
        self.ai = AIProviderManager() if AIProviderManager else None
        self.plugins = PluginManager() if PluginManager else None
        self.log_queue: queue.Queue = queue.Queue()
        self.log_streamer: Optional[LogStreamer] = None
        self.processes: Dict[str, subprocess.Popen] = {}
        self.chat_history: List[List[str]] = []
        self._agent_bridge = AgentBridge(ROOT) if AgentBridge else None
        self._fixer = AutoFixer(ROOT) if AutoFixer else None
        self._init_log: List[str] = []
        self.mobile = MobilePrep() if MobilePrep else None
        if self.mobile:
            self.mobile.detect_mobile()
        self.brain = AuraBrain() if AuraBrain else None
        self.brain_api = AuraBrainAPI() if AuraBrainAPI else None
        if self.brain:
            self.brain.load_model()
        self.orchestrator = BrainOrchestrator(
            brain=self.brain,
            brain_api=self.brain_api,
            ai_manager=self.ai,
        ) if BrainOrchestrator else None

        if AutoFixer is None:
            self._init_log.append("[WARN] agent_bridge.py not found — Repair tab will be limited.")
        if EmbeddedAuraBackend is None:
            self._init_log.append("[WARN] backend_embedded.py not found — Chat will fallback to HTTP.")
        if AIProviderManager is None:
            self._init_log.append("[WARN] ai_providers.py not found — AI limited.")
        elif self.ai:
            available = self.ai.get_available_providers()
            if available:
                self._init_log.append(f"[AI] Providers available: {', '.join(available)}")
            else:
                self._init_log.append("[AI] No external AI providers configured. Using local fallback.")
        if PluginManager is None:
            self._init_log.append("[WARN] aura_plugin_system.py not found — Plugins disabled.")

        self._build_ui()
        if self.mobile and self.mobile.is_mobile:
            self.root.attributes("-fullscreen", True)
        self._start_log_streamer()
        self._poll_logs()
        self._update_status_periodically()
        self._show_welcome()
        self._flush_init_log()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=TEXT2, padding=[14, 8])
        style.map("TNotebook.Tab", background=[("selected", ACCENT2)],
                         foreground=[("selected", "#fff")])
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT)
        style.configure("TButton", font=FONT_BOLD, padding=6)
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                         font=FONT, rowheight=26)
        style.configure("Treeview.Heading", background=PANEL2, foreground=ACCENT,
                         font=FONT_BOLD, padding=4)

        # === HEADER BAR ===
        header = tk.Frame(self.root, bg=PANEL, height=90)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # Left: App branding
        brand = tk.Frame(header, bg=PANEL)
        brand.pack(side=tk.LEFT, padx=16, pady=8)
        tk.Label(
            brand, text="◆", font=("Segoe UI", 20, "bold"),
            bg=PANEL, fg=ACCENT2,
        ).pack(side=tk.LEFT)
        tk.Label(
            brand, text="AURA", font=FONT_TITLE,
            bg=PANEL, fg=ACCENT2,
        ).pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(
            brand, text="OS", font=("Segoe UI", 12, "bold"),
            bg=PANEL, fg=TEXT_DIM,
        ).pack(side=tk.LEFT, padx=(2, 0))

        # Center: Nucleus canvas
        self.nucleus = NucleusCanvas(header, width=180, height=70)
        self.nucleus.widget().pack(side=tk.LEFT, expand=True, padx=8)

        # Right: Status + telemetry
        right_frame = tk.Frame(header, bg=PANEL)
        right_frame.pack(side=tk.RIGHT, padx=16, pady=8)
        self.status_var = tk.StringVar(value="● Checking...")
        self.status_label = tk.Label(
            right_frame, textvariable=self.status_var,
            font=FONT_BOLD, bg=PANEL, fg=GREEN,
        )
        self.status_label.pack(anchor="e", pady=(0, 4))

        # Telemetry mini bar
        tel_frame = tk.Frame(right_frame, bg=BG2)
        tel_frame.pack(fill=tk.X, pady=(0, 0))
        self.cpu_label = tk.Label(tel_frame, text="CPU: --", font=FONT_MONO, bg=BG2, fg=BLUE)
        self.cpu_label.pack(side=tk.LEFT, padx=4)
        self.ram_label = tk.Label(tel_frame, text="RAM: --", font=FONT_MONO, bg=BG2, fg=ACCENT)
        self.ram_label.pack(side=tk.LEFT, padx=4)
        self.model_label = tk.Label(tel_frame, text="Model: --", font=FONT_MONO, bg=BG2, fg=ACCENT2)
        self.model_label.pack(side=tk.LEFT, padx=4)
        self.agents_label = tk.Label(tel_frame, text="Agents: --", font=FONT_MONO, bg=BG2, fg=GREEN)
        self.agents_label.pack(side=tk.LEFT, padx=4)

        # === MAIN NOTEBOOK ===
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.tab_chat = tk.Frame(self.nb, bg=BG)
        self.tab_services = tk.Frame(self.nb, bg=BG)
        self.tab_training = tk.Frame(self.nb, bg=BG)
        self.tab_logs = tk.Frame(self.nb, bg=BG)
        self.tab_settings = tk.Frame(self.nb, bg=BG)
        self.tab_repair = tk.Frame(self.nb, bg=BG)
        self.tab_agents = tk.Frame(self.nb, bg=BG)
        self.tab_voice = tk.Frame(self.nb, bg=BG)
        self.tab_gesture = tk.Frame(self.nb, bg=BG)
        self.tab_vision = tk.Frame(self.nb, bg=BG)
        self.tab_osint = tk.Frame(self.nb, bg=BG)
        self.tab_plugins = tk.Frame(self.nb, bg=BG)
        self.tab_particles = tk.Frame(self.nb, bg=BG)

        self.nb.add(self.tab_chat, text="💬 Chat")
        self.nb.add(self.tab_services, text="⚙ Services")
        self.nb.add(self.tab_training, text="🎓 Training")
        self.nb.add(self.tab_logs, text="📋 Logs")
        self.nb.add(self.tab_settings, text="🔧 Settings")
        self.nb.add(self.tab_repair, text="🔨 Repair")
        self.nb.add(self.tab_agents, text="🤖 Agents")
        self.nb.add(self.tab_voice, text="🎤 Voice")
        self.nb.add(self.tab_gesture, text="✋ Gestures")
        self.nb.add(self.tab_vision, text="👁 Vision")
        self.nb.add(self.tab_osint, text="🌐 OSINT")
        self.nb.add(self.tab_plugins, text="🧩 Plugins")
        self.nb.add(self.tab_particles, text="✨ 3D Particles")

        self._build_chat_tab()
        self._build_services_tab()
        self._build_training_tab()
        self._build_logs_tab()
        self._build_settings_tab()
        self._build_repair_tab()
        self._build_agents_tab()
        self._build_voice_tab()
        self._build_gesture_tab()
        self._build_vision_tab()
        self._build_osint_tab()
        self._build_plugins_tab()
        self._build_particles_tab()

    # ------------------------------------------------------------------
    # Chat tab — modern redesign
    # ------------------------------------------------------------------
    def _build_chat_tab(self) -> None:
        frame = self.tab_chat
        frame.configure(bg=BG)

        # Chat history
        chat_frame = tk.Frame(frame, bg=BG)
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 8))

        self.chat_display = tk.Text(
            chat_frame,
            bg=PANEL,
            fg=TEXT,
            font=FONT,
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=16,
            pady=16,
            insertbackground=ACCENT,
            selectbackground=ACCENT,
            selectforeground="white",
        )
        scrollbar = ttk.Scrollbar(chat_frame, command=self.chat_display.yview)
        self.chat_display.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for modern styling
        self.chat_display.tag_configure("user_msg",
            foreground=ACCENT, font=FONT_BOLD,
            backoverlaps=False,
        )
        self.chat_display.tag_configure("bot_msg",
            foreground=TEXT, font=FONT,
        )
        self.chat_display.tag_configure("timestamp",
            foreground=TEXT_DIM, font=FONT_MONO,
        )
        self.chat_display.tag_configure("system_msg",
            foreground=YELLOW, font=FONT_BOLD,
        )
        self.chat_display.tag_configure("sep",
            foreground=TEXT_DIM, font=("Segoe UI", 7),
        )

        # Input area
        input_frame = tk.Frame(frame, bg=BG)
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.chat_input = tk.Entry(
            input_frame,
            bg=PANEL,
            fg=TEXT,
            font=FONT,
            insertbackground=ACCENT,
            relief=tk.FLAT,
            selectbackground=ACCENT,
            selectforeground="white",
        )
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True,
                               padx=(0, 8), ipady=8)
        self.chat_input.bind("<Return>", lambda e: self._send_chat())

        btn_send = tk.Button(
            input_frame,
            text="▶ Enviar",
            command=self._send_chat,
            bg=ACCENT2, fg="white",
            font=FONT_BOLD, relief=tk.FLAT, padx=16, ipady=4,
            activebackground=ACCENT, activeforeground="white",
            cursor="hand2",
        )
        btn_send.pack(side=tk.RIGHT, padx=(0, 4))

        btn_clear = tk.Button(
            input_frame,
            text="Clear",
            command=lambda: self.chat_display.config(state=tk.NORMAL) or self.chat_display.delete("1.0", tk.END) or self.chat_display.config(state=tk.DISABLED),
            bg=PANEL2, fg=TEXT2,
            font=FONT, relief=tk.FLAT, padx=12, ipady=4,
            activebackground=PANEL, activeforeground=TEXT,
            cursor="hand2",
        )
        btn_clear.pack(side=tk.RIGHT, padx=(0, 4))

    def _send_chat(self) -> None:
        msg = self.chat_input.get().strip()
        if not msg:
            return
        self.chat_input.delete(0, tk.END)
        self._append_chat("user", msg)
        self.chat_history.append([msg, ""])
        self._turn_begin_voice()   # Fase 3: turno nuevo -> TTS fresco
        if self.nucleus:
            self.nucleus.set_status("thinking")
            self.nucleus.react()
        threading.Thread(target=self._chat_worker, args=(msg,), daemon=True).start()

    def _chat_worker(self, message: str) -> None:
        lower = message.lower()
        if lower == "/clear":
            self.embedded.reset() if self.embedded else None
            self.chat_history.clear()
            bot_msg = "Historial limpiado."
        elif self.orchestrator:
            result = self.orchestrator.chat(message, self.chat_history)
            bot_msg = result.get("message", "Sin respuesta")
        elif self.ai:
            resp = self.ai.chat(message, self.chat_history)
            bot_msg = resp.get("message", "Sin respuesta")
        elif self.embedded:
            resp = self.embedded.chat(message)
            bot_msg = resp.get("message", "Sin respuesta")
        else:
            bot_msg = self._stream_chat(message)
        self.chat_history[-1][1] = bot_msg
        if self.nucleus:
            self.nucleus.set_status("speaking")
            self.nucleus.react()
        self.root.after(0, lambda: self._append_chat("bot", bot_msg))
        self.root.after(500, self._await_tts_idle)

    def _turn_begin_voice(self) -> None:
        """Fase 3: resetea el TTS incremental al inicio de cada turno del chat."""
        self._tts_turn_begin()

    def _stream_chat(self, message: str) -> str:
        """Streaming SSE desde /api/chat/stream, energizando el núcleo por token.

        Si el stream no está disponible se cae a la ruta bloqueante /api/chat.
        """
        chunks: List[str] = []
        try:
            self.client.chat_stream(
                message,
                self.chat_history,
                system_prompt=SYSTEM_PROMPT,
                on_token=lambda piece: self._on_stream_token(piece, chunks),
            )
            text = "".join(chunks).strip()
            if text:
                self._tts_turn_flush()   # habla el resto; el núcleo espera al TTS
                return text
            raise RuntimeError("respuesta vacía del stream")
        except Exception as exc:
            self._log(f"[stream] fallo ({exc}) · usando /api/chat")
        resp = self.client.chat(message, self.chat_history)
        return resp.get("message") or resp.get("error", "No response")

    def _on_stream_token(self, piece: str, chunks: List[str]) -> None:
        """Acumula cada token del stream y hace reaccionar el núcleo (hilo worker)."""
        chunks.append(piece)
        self._tts_turn_feed(piece)   # Fase 3: TTS token-a-token, sin esperar al final
        if self.nucleus:
            self.nucleus.on_token(piece)

    def _await_tts_idle(self) -> None:
        """Fase 3: el núcleo queda en 'speaking' hasta que el TTS drene la cola."""
        if self._tts_is_busy():
            self.root.after(400, self._await_tts_idle)
            return
        self._nucleus_idle()

    def _nucleus_idle(self) -> None:
        """Devuelve el núcleo a reposo tras terminar de hablar."""
        if self.nucleus and self.nucleus.status in ("speaking", "thinking"):
            self.nucleus.set_status("ready")
            self.nucleus.react()

    def _capture_training_sample(self, user_msg: str, bot_msg: str) -> None:
        try:
            if not self.brain:
                return
            should_capture = True
            if user_msg.startswith("/"):
                should_capture = False
            if len(user_msg) < 3 or len(bot_msg) < 5:
                should_capture = False
            if not should_capture:
                return
            saved = self.brain.add_training_sample(user_msg, bot_msg)
            if saved:
                status = self.brain.get_training_status()
                samples = status.get("samples", 0)
                if samples % 20 == 0:
                    self._log(f"[TRAIN] Captured {samples} samples for auto-training")
        except Exception:
            pass

    def _brain_chat(self, message: str) -> str:
        try:
            if self.brain_api and self.brain_api.get_best_provider():
                provider = self.brain_api.get_best_provider()
                start = time.time()
                if self.ai and hasattr(self.ai, "chat"):
                    resp = self.ai.chat(message, self.chat_history, provider=provider)
                    latency = time.time() - start
                    self.brain_api.mark_success(provider, latency)
                    text = resp.get("message", "")
                    if text:
                        return text
                self.brain_api.mark_failure(provider)
            if self.brain and self.brain.model_loaded:
                response = self.brain.generate(message)
                if response:
                    return response
            if self.ai:
                resp = self.ai.chat(message, self.chat_history)
                return resp.get("message", "Sin respuesta")
            if self.embedded:
                resp = self.embedded.chat(message)
                return resp.get("message", "Sin respuesta")
            return "Sin respuesta del cerebro."
        except Exception as e:
            return f"[BRAIN ERROR] {e}"

    def _append_chat(self, role: str, text: str) -> None:
        self.chat_display.config(state=tk.NORMAL)
        ts = time.strftime("%H:%M:%S")
        # Separator line
        self.chat_display.insert(tk.END, "─" * 60 + "\n", "sep")
        # Timestamp
        self.chat_display.insert(tk.END, f" {ts} ", "timestamp")
        if role == "user":
            self.chat_display.insert(tk.END, " YOU\n", "user_msg")
            self.chat_display.insert(tk.END, f"  {text}\n\n", "bot_msg")
        elif role == "system":
            self.chat_display.insert(tk.END, " SYSTEM\n", "system_msg")
            self.chat_display.insert(tk.END, f"  {text}\n\n", "bot_msg")
        else:
            self.chat_display.insert(tk.END, " AURA ⚡\n", "system_msg")
            self.chat_display.insert(tk.END, f"  {text}\n\n", "bot_msg")
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Services tab
    # ------------------------------------------------------------------
    def _build_services_tab(self) -> None:
        frame = self.tab_services
        frame.configure(bg=BG)

        top = tk.Frame(frame, bg=BG)
        top.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(
            top, text="Refresh", command=self._refresh_services,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.RIGHT)

        self.services_tree = ttk.Treeview(frame, columns=("status", "updated"), show="tree headings")
        self.services_tree.heading("#0", text="Service")
        self.services_tree.heading("status", text="Status")
        self.services_tree.heading("updated", text="Updated")
        self.services_tree.column("#0", width=220)
        self.services_tree.column("status", width=120)
        self.services_tree.column("updated", width=180)
        self.services_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        for svc in ["backend", "frontend", "discord-bot", "hf-space"]:
            tk.Button(
                btn_frame, text=f"Start {svc}", command=lambda s=svc: self._start_service(s),
                bg=PANEL, fg=TEXT, font=FONT, relief=tk.FLAT, padx=10
            ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            btn_frame, text="Stop Selected", command=self._stop_selected_service,
            bg=RED, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.RIGHT)

        self._refresh_services()

    def _refresh_services(self) -> None:
        self.services_tree.delete(*self.services_tree.get_children())
        if self.embedded:
            stats = self.embedded.get_stats()
            self.services_tree.insert("", tk.END, text="backend (embedded)", values=(stats.get("status", "active"), "local"), tags=("ok",))
        else:
            self.services_tree.insert("", tk.END, text="backend", values=("unavailable", "embedded disabled"), tags=("bad",))
        for name, payload in self.client.status().items():
            if name == "error":
                continue
            status = payload.get("status", "unknown") if isinstance(payload, dict) else str(payload)
            updated = payload.get("updated_at", "") if isinstance(payload, dict) else ""
            tag = "ok" if status == "ok" else "bad"
            self.services_tree.insert("", tk.END, text=name, values=(status, str(updated)), tags=(tag,))
        self.services_tree.tag_configure("ok", foreground=GREEN)
        self.services_tree.tag_configure("bad", foreground=RED)

    def _start_service(self, svc: str) -> None:
        if svc == "backend":
            if not self.embedded:
                messagebox.showerror("Error", "Embedded backend not available")
                return
            self._log("Embedded backend is already active")
            messagebox.showinfo("Backend", "Backend embebido ya está activo en memoria")
            return
        cmds = {
            "frontend": ["npm", "run", "dev"],
            "discord-bot": ["ruby", "bot.rb"],
            "hf-space": ["python", "app.py"],
        }
        cmd = cmds.get(svc)
        if not cmd:
            return
        cwd = ROOT / {"backend": ".", "frontend": "frontend", "discord-bot": "services/discord-bot", "hf-space": "hf-space"}[svc]
        try:
            p = subprocess.Popen(cmd, cwd=str(cwd), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.processes[svc] = p
            self._log(f"Started {svc} (pid {p.pid})")
        except Exception as exc:
            messagebox.showerror("Start failed", str(exc))

    def _stop_selected_service(self) -> None:
        sel = self.services_tree.selection()
        if not sel:
            return
        name = self.services_tree.item(sel[0], "text")
        p = self.processes.get(name)
        if p and p.poll() is None:
            p.terminate()
            self._log(f"Stopped {name}")

    # ------------------------------------------------------------------
    # Training tab
    # ------------------------------------------------------------------
    def _build_training_tab(self) -> None:
        frame = self.tab_training
        frame.configure(bg=BG)

        form = tk.Frame(frame, bg=BG)
        form.pack(fill=tk.X, padx=12, pady=12)

        tk.Label(form, text="Model", bg=BG, fg=TEXT, font=FONT).grid(row=0, column=0, sticky="w", pady=4)
        self.model_var = tk.StringVar(value="Qwen/Qwen2.5-1.5B-Instruct")
        tk.Entry(form, textvariable=self.model_var, bg=PANEL, fg=TEXT, font=FONT, relief=tk.FLAT).grid(
            row=0, column=1, sticky="ew", padx=8, pady=4
        )

        tk.Label(form, text="Dataset", bg=BG, fg=TEXT, font=FONT).grid(row=1, column=0, sticky="w", pady=4)
        self.dataset_var = tk.StringVar(value="training-data.jsonl")
        tk.Entry(form, textvariable=self.dataset_var, bg=PANEL, fg=TEXT, font=FONT, relief=tk.FLAT).grid(
            row=1, column=1, sticky="ew", padx=8, pady=4
        )

        tk.Label(form, text="Output", bg=BG, fg=TEXT, font=FONT).grid(row=2, column=0, sticky="w", pady=4)
        self.output_var = tk.StringVar(value="fine-tuned-ame")
        tk.Entry(form, textvariable=self.output_var, bg=PANEL, fg=TEXT, font=FONT, relief=tk.FLAT).grid(
            row=2, column=1, sticky="ew", padx=8, pady=4
        )

        form.columnconfigure(1, weight=1)

        btn = tk.Button(
            form, text="Start Training", command=self._start_training,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=16
        )
        btn.grid(row=3, column=0, columnspan=2, pady=12, sticky="ew")

        self.training_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        self.training_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

    def _start_training(self) -> None:
        def worker():
            resp = self.client.start_training(
                self.model_var.get(),
                self.dataset_var.get(),
                self.output_var.get(),
            )
            msg = resp.get("message") or resp.get("error", "Unknown")
            self.root.after(0, lambda: self._append_training(f"TRAINING: {msg}\n"))
            self.root.after(0, self._refresh_training_status)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_training_status(self) -> None:
        data = self.client.training_status()
        self._append_training(json.dumps(data, indent=2) + "\n")

    def _append_training(self, text: str) -> None:
        self.training_output.config(state=tk.NORMAL)
        self.training_output.insert(tk.END, text)
        self.training_output.see(tk.END)
        self.training_output.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Logs tab
    # ------------------------------------------------------------------
    def _build_logs_tab(self) -> None:
        frame = self.tab_logs
        frame.configure(bg=BG)

        toolbar = tk.Frame(frame, bg=BG)
        toolbar.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(
            toolbar, text="Refresh", command=self._refresh_logs,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.RIGHT)

        self.log_display = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.log_display.yview)
        self.log_display.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _start_log_streamer(self) -> None:
        self.log_streamer = LogStreamer(self.log_queue)
        self.log_streamer.start()

    def _poll_logs(self) -> None:
        try:
            while True:
                kind, value = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(value)
        except queue.Empty:
            pass
        self.root.after(500, self._poll_logs)

    def _append_log(self, text: str) -> None:
        self.log_display.config(state=tk.NORMAL)
        self.log_display.insert(tk.END, text + "\n")
        self.log_display.see(tk.END)
        # limit size
        lines = int(self.log_display.index("end-1c").split(".")[0])
        if lines > 5000:
            self.log_display.delete("1.0", "1000.0")
        self.log_display.config(state=tk.DISABLED)

    def _refresh_logs(self) -> None:
        data = self.client.logs()
        logs = data.get("logs", data.get("error", "No logs"))
        self._append_log(logs)

    # ------------------------------------------------------------------
    # Settings tab
    # ------------------------------------------------------------------
    def _build_settings_tab(self) -> None:
        frame = self.tab_settings
        frame.configure(bg=BG)

        tk.Label(frame, text="AURA Configuration", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        self.settings_text = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, relief=tk.FLAT, padx=12, pady=12
        )
        self.settings_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Button(
            btn_frame, text="Load .env", command=self._load_env,
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Save .env", command=self._save_env,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self._load_env()

    def _load_env(self) -> None:
        env_path = ROOT / ".env"
        self.settings_text.delete("1.0", tk.END)
        if env_path.exists():
            try:
                self.settings_text.insert(tk.END, env_path.read_text(encoding="utf-8", errors="ignore"))
            except PermissionError:
                self.settings_text.insert(tk.END, "# Permission denied reading .env\n# Check file permissions")

    def _save_env(self) -> None:
        env_path = ROOT / ".env"
        env_path.write_text(self.settings_text.get("1.0", tk.END), encoding="utf-8")
        messagebox.showinfo("Saved", ".env updated. Restart services to apply.")

    # ------------------------------------------------------------------
    # Repair tab
    # ------------------------------------------------------------------
    def _build_repair_tab(self) -> None:
        frame = self.tab_repair
        frame.configure(bg=BG)

        tk.Label(frame, text="VS Code & Project Auto-Repair", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Button(
            btn_frame, text="Scan Issues", command=self._repair_scan,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Auto-Fix", command=self._repair_auto_fix,
            bg=GREEN, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Run PowerShell Fixer", command=self._repair_run_ps1,
            bg=YELLOW, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self.repair_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.repair_output.yview)
        self.repair_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.repair_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._repair_append("[READY] Repair system initialized.\n")

    def _repair_append(self, text: str) -> None:
        self.repair_output.config(state=tk.NORMAL)
        self.repair_output.insert(tk.END, text + "\n")
        self.repair_output.see(tk.END)
        self.repair_output.config(state=tk.DISABLED)

    def _repair_scan(self) -> None:
        def worker():
            if AutoFixer is None:
                self.root.after(0, lambda: self._repair_append("[ERROR] agent_bridge.py not found.\n"))
                return
            self.root.after(0, lambda: self._repair_append("[SCAN] Running diagnostic...\n"))
            fixer = AutoFixer(ROOT)
            issues = fixer.scan()
            self.root.after(0, lambda: self._repair_append(f"[SCAN] Found {len(issues)} issue(s).\n"))
            for issue in issues:
                sev = issue.get("severity", "info").upper()
                self.root.after(0, lambda i=issue, s=sev: self._repair_append(f"  [{s}] {i['type']}: {i['message']} ({i['file']})\n"))
            if not issues:
                self.root.after(0, lambda: self._repair_append("[SCAN] No issues found. System OK.\n"))
        threading.Thread(target=worker, daemon=True).start()

    def _repair_auto_fix(self) -> None:
        def worker():
            if AutoFixer is None:
                self.root.after(0, lambda: self._repair_append("[ERROR] agent_bridge.py not found.\n"))
                return
            self.root.after(0, lambda: self._repair_append("[FIX] Attempting automatic repairs...\n"))
            fixer = AutoFixer(ROOT)
            fixer.scan()
            fixes = fixer.auto_fix()
            self.root.after(0, lambda: self._repair_append(f"[FIX] Applied {len(fixes)} fix(es).\n"))
            for fix in fixes:
                self.root.after(0, lambda f=fix: self._repair_append(f"  [OK] {f}\n"))
        threading.Thread(target=worker, daemon=True).start()

    def _repair_run_ps1(self) -> None:
        ps1 = ROOT / "fix_vscode_errors.ps1"
        if not ps1.exists():
            messagebox.showerror("Missing", "fix_vscode_errors.ps1 not found")
            return
        self._repair_append("[POWERSHELL] Running fix_vscode_errors.ps1 ...\n")
        def worker():
            try:
                proc = subprocess.run(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                out = proc.stdout.strip()
                err = proc.stderr.strip()
                if out:
                    self.root.after(0, lambda: self._repair_append(out))
                if err:
                    self.root.after(0, lambda: self._repair_append(f"[STDERR] {err[:500]}"))
                self.root.after(0, lambda: self._repair_append("[POWERSHELL] Done.\n"))
            except Exception as exc:
                self.root.after(0, lambda: self._repair_append(f"[ERROR] {exc}\n"))
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Agents tab
    # ------------------------------------------------------------------
    def _build_agents_tab(self) -> None:
        frame = self.tab_agents
        frame.configure(bg=BG)

        tk.Label(frame, text="Code Agents (Kilo / Cline)", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        # Agent selection
        sel_frame = tk.Frame(frame, bg=BG)
        sel_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(sel_frame, text="Agent:", bg=BG, fg=TEXT, font=FONT).pack(side=tk.LEFT, padx=(0, 8))
        self.agent_var = tk.StringVar(value="kilo")
        self.agent_combo = ttk.Combobox(sel_frame, textvariable=self.agent_var, state="readonly")
        self.agent_combo.pack(side=tk.LEFT, padx=(0, 8))

        self.agent_status_var = tk.StringVar(value="Detecting...")
        tk.Label(sel_frame, textvariable=self.agent_status_var, bg=BG, fg=TEXT_DIM, font=FONT).pack(side=tk.RIGHT)

        # Prompt
        tk.Label(frame, text="Prompt:", bg=BG, fg=TEXT, font=FONT).pack(anchor="w", padx=12)
        self.agent_prompt = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT, height=6, relief=tk.FLAT, padx=8, pady=8
        )
        self.agent_prompt.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Button(
            btn_frame, text="Send Prompt", command=self._agent_send,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=16
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Fix Errors in Project", command=self._agent_fix_errors,
            bg=GREEN, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=16
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Scan Project", command=self._agent_scan,
            bg=YELLOW, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=16
        ).pack(side=tk.LEFT)

        # Output
        self.agent_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.agent_output.yview)
        self.agent_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.agent_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._refresh_agent_list()

    def _refresh_agent_list(self) -> None:
        if not self._agent_bridge:
            self.agent_combo["values"] = []
            self.agent_status_var.set("Agent bridge unavailable")
            return
        available = self._agent_bridge.get_available_agents()
        self.agent_combo["values"] = available
        if available:
            self.agent_var.set(available[0])
            self.agent_status_var.set(f"Available: {', '.join(available)}")
        else:
            self.agent_status_var.set("No agents detected")

    def _agent_append(self, text: str) -> None:
        self.agent_output.config(state=tk.NORMAL)
        self.agent_output.insert(tk.END, text + "\n")
        self.agent_output.see(tk.END)
        self.agent_output.config(state=tk.DISABLED)

    def _agent_send(self) -> None:
        agent = self.agent_var.get()
        prompt = self.agent_prompt.get("1.0", tk.END).strip()
        if not prompt or not self._agent_bridge or not self._agent_bridge.is_available(agent):
            return
        self._agent_bridge.start_worker()
        task = self._agent_bridge.create_task(agent, prompt)
        self._agent_append(f"[{agent.upper()}] Task {task.task_id} started...")
        self.root.after(500, lambda: self._agent_poll_task(task.task_id))

    def _agent_poll_task(self, task_id: str) -> None:
        if not self._agent_bridge:
            return
        task = self._agent_bridge.get_task(task_id)
        if not task:
            return
        if task.status == "running":
            self.root.after(500, lambda: self._agent_poll_task(task_id))
            return
        if task.status == "completed":
            self._agent_append(f"[RESULT]\n{task.result}\n")
        elif task.status == "failed":
            self._agent_append(f"[ERROR] {task.error}\n")

    def _agent_fix_errors(self) -> None:
        self.agent_prompt.delete("1.0", tk.END)
        self.agent_prompt.insert(tk.END, "Scan the project for errors in Python, TypeScript, Ruby, and VS Code config. Fix all fixable issues automatically. Report what you changed.")
        self._agent_send()

    def _agent_scan(self) -> None:
        self.agent_prompt.delete("1.0", tk.END)
        self.agent_prompt.insert(tk.END, "Scan this AURA project structure and report: 1) missing dependencies, 2) syntax errors, 3) config issues, 4) broken imports. Do not fix anything, just report.")
        self._agent_send()

    # ------------------------------------------------------------------
    # Voice tab
    # ------------------------------------------------------------------
    def _build_voice_tab(self) -> None:
        frame = self.tab_voice
        frame.configure(bg=BG)

        tk.Label(frame, text="Voice Assistant (JARVIS-style)", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.voice_engine = VoiceEngine() if VoiceEngine else None
        if self.voice_engine:
            # Fase 3: el wake word dispara el chat real (texto -> _send_chat),
            # no solo el ejecutor de comandos simulados del motor de voz.
            self.voice_engine.on_wake_command = self._voice_command_to_chat
        self.voice_auto_speak = tk.BooleanVar(value=True)

        self.voice_status_var = tk.StringVar(value="Inactive")
        tk.Label(btn_frame, textvariable=self.voice_status_var, bg=BG, fg=TEXT_DIM, font=FONT).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame, text="Start Listening", command=self._voice_start,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Stop", command=self._voice_stop,
            bg=RED, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Speak Test", command=lambda: self._voice_speak("Hola, soy AURA. ¿En qué puedo ayudarte?"),
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        tk.Checkbutton(
            btn_frame, text="Auto-hablar respuestas",
            variable=self.voice_auto_speak, bg=BG, fg=TEXT_DIM,
            activebackground=BG, selectcolor=PANEL, font=FONT,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.voice_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.voice_output.yview)
        self.voice_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.voice_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        if self.voice_engine:
            caps = self.voice_engine.get_capabilities()
            cap_str = f"STT={'ON' if caps['stt'] else 'OFF'} | TTS={'ON' if caps['tts'] else 'OFF'} | Mic={'ON' if caps['mic'] else 'OFF'}"
            self._voice_append(f"[READY] Voice engine initialized. Wake-word: 'hey aura'")
            self._voice_append(f"[CAPS] {cap_str}")
            if not caps['stt']:
                self._voice_append("[WARN] Install SpeechRecognition + pyaudio for real microphone input")
        else:
            self._voice_append("[ERROR] Voice engine not available.")

        self._poll_voice()

    def _voice_start(self) -> None:
        if not self.voice_engine:
            return
        self.voice_engine.start_listening()
        self.voice_status_var.set("Listening...")
        self._voice_append("[LISTENING] Wake word: 'hey aura'")
        if self.nucleus:
            self.nucleus.set_status("listening")
            self.nucleus.react()

    def _voice_stop(self) -> None:
        if not self.voice_engine:
            return
        self.voice_engine.stop_listening()
        self.voice_status_var.set("Stopped")
        self._voice_append("[STOPPED]")
        if self.nucleus:
            self.nucleus.set_status("ready")
            self.nucleus.react()

    def _voice_command_to_chat(self, spoken_text: str) -> None:
        """Fase 3: el wake word entra al chat real. Quita el wake word con el
        backend (/api/voice/wake) y manda el comando limpio; si no hay comando
        (solo dijeron el wake), el texto completo va igual al chat."""
        command = ""
        try:
            body = json.dumps({"text": spoken_text}).encode()
            req = urllib.request.Request(
                f"{self.client.base_url}/api/voice/wake",
                data=body, headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            command = (data.get("command") or "").strip()
        except Exception:
            command = ""
        msg = command or spoken_text.strip()
        if not msg:
            return
        self.root.after(0, lambda: self._inject_chat_message(msg))

    def _inject_chat_message(self, msg: str) -> None:
        """Inyecta un mensaje de voz en el chat como si lo hubiera escrito el usuario."""
        if not msg:
            return
        self.nb.select(self.tab_chat)
        self.chat_input.delete(0, tk.END)
        self.chat_input.insert(0, msg)
        self._send_chat()

    # ---------- Fase 3: TTS incremental durante el stream ----------
    def _tts_turn_begin(self) -> None:
        ve = self.voice_engine
        if ve is None or not getattr(self, "voice_auto_speak", None):
            return
        try:
            if self.voice_auto_speak.get() and ve.tts_stream.available():
                ve.tts_stream.start_turn()
            else:
                ve.tts_stream.stop()
        except Exception:
            pass

    def _tts_turn_feed(self, piece: str) -> None:
        ve = self.voice_engine
        if ve is None:
            return
        try:
            if getattr(self, "voice_auto_speak", None) and self.voice_auto_speak.get():
                for sentence in ve.tts_stream.feed(piece or ""):
                    self._voice_append(f"[TTS»] {sentence[:90]}")
        except Exception:
            pass

    def _tts_turn_flush(self) -> None:
        ve = self.voice_engine
        if ve is None:
            return
        try:
            if getattr(self, "voice_auto_speak", None) and self.voice_auto_speak.get():
                for sentence in ve.tts_stream.flush():
                    self._voice_append(f"[TTS»] {sentence[:90]}")
            else:
                ve.tts_stream.stop()
        except Exception:
            pass

    def _tts_is_busy(self) -> bool:
        try:
            return bool(self.voice_engine and self.voice_engine.tts_stream.is_busy())
        except Exception:
            return False

    def _voice_speak(self, text: str) -> None:
        if not self.voice_engine:
            return
        self.voice_engine.speak(text)
        self._voice_append(f"[TTS] {text}")
        if self.nucleus:
            self.nucleus.set_status("speaking")
            self.nucleus.react()

    def _voice_append(self, text: str) -> None:
        self.voice_output.config(state=tk.NORMAL)
        self.voice_output.insert(tk.END, text + "\n")
        self.voice_output.see(tk.END)
        self.voice_output.config(state=tk.DISABLED)

    def _poll_voice(self) -> None:
        if self.voice_engine:
            for ev in self.voice_engine.get_events():
                kind = ev.get("type")
            for ev in self.voice_engine.get_events():
                kind = ev.get("type")
                if kind == "transcript":
                    src = ev.get("source", "?")
                    self._voice_append(f"[STT:{src}] {ev.get('text', '')}")
                    if self.nucleus:
                        self.nucleus.set_status("listening")
                        self.nucleus.react()
                elif kind == "mic_error":
                    self._voice_append(f"[MIC-ERROR] {ev.get('text', '')}")
                    self.voice_status_var.set("Mic error")
                elif kind == "stt_error":
                    self._voice_append(f"[STT-ERROR] {ev.get('text', '')}")
                elif kind == "wake_word":
                    self._voice_append(f"[WAKE] Detected: {ev.get('text', '')}")
                elif kind == "command":
                    cmd = ev.get("command", "unknown")
                    self._voice_append(f"[CMD] {cmd}")
                    result = self.voice_engine.execute_command(cmd)
                    self._voice_append(f"[RESP] {result.get('response', '')}")
                elif kind == "tts":
                    self._voice_append(f"[TTS] {ev.get('text', '')}")
        self.root.after(500, self._poll_voice)

    # ------------------------------------------------------------------
    # Gestures tab
    # ------------------------------------------------------------------
    def _build_gesture_tab(self) -> None:
        frame = self.tab_gesture
        frame.configure(bg=BG)

        tk.Label(frame, text="Gesture Recognition + Overlays", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.gesture_engine = GestureEngine() if GestureEngine else None

        self.gesture_status_var = tk.StringVar(value="Inactive")
        tk.Label(btn_frame, textvariable=self.gesture_status_var, bg=BG, fg=TEXT_DIM, font=FONT).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame, text="Start Camera", command=self._gesture_start,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Stop", command=self._gesture_stop,
            bg=RED, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Toggle Overlay", command=self._gesture_toggle_overlay,
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self.gesture_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.gesture_output.yview)
        self.gesture_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.gesture_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        if self.gesture_engine:
            self._gesture_append("[READY] Gesture engine initialized. Supported: open_hand, fist, index, peace.")
        else:
            self._gesture_append("[ERROR] Gesture engine not available. Install opencv-python and mediapipe.")

        self._poll_gesture()

    def _gesture_start(self) -> None:
        if not self.gesture_engine:
            return
        self.gesture_engine.start()
        self.gesture_status_var.set("Running")
        self._gesture_append("[STARTED] Camera active. Show gestures to the camera.")
        try:
            self.gesture_engine.add_gesture_callback(self._on_gesture_for_particles)
        except Exception:
            pass

    def _gesture_stop(self) -> None:
        if not self.gesture_engine:
            return
        self.gesture_engine.stop()
        self.gesture_status_var.set("Stopped")
        self._gesture_append("[STOPPED]")

    def _on_gesture_for_particles(self, gesture: str, confidence: float, fingers: int) -> None:
        try:
            self.current_gesture = gesture
            self.current_gesture_conf = confidence
            pos = getattr(self.gesture_engine, "hand_center", None)
            if pos is None:
                pos = (0.0, 0.0, 0.0)
            self.current_gesture_pos = pos
            engine = getattr(self, "particle_engine", None)
            domain = getattr(self, "domain", None)
            if engine and gesture != "none":
                engine.set_gesture(gesture, pos[0], pos[1], pos[2], confidence)
            if domain and gesture != "none":
                expanded = domain.expand(gesture, pos[0], pos[1], pos[2])
                if expanded:
                    try:
                        from domain_expansion import DOMAINS
                        name = DOMAINS.get(gesture).name if gesture in DOMAINS else ""
                        self._particles_append(f"[DOMAIN EXPANSION] {name}")
                    except Exception:
                        pass
        except Exception:
            pass

    def _gesture_toggle_overlay(self) -> None:
        if not self.gesture_engine:
            return
        self.gesture_engine.overlay_mode = not self.gesture_engine.overlay_mode
        state = "ON" if self.gesture_engine.overlay_mode else "OFF"
        self._gesture_append(f"[OVERLAY] {state}")

    def _gesture_append(self, text: str) -> None:
        self.gesture_output.config(state=tk.NORMAL)
        self.gesture_output.insert(tk.END, text + "\n")
        self.gesture_output.see(tk.END)
        self.gesture_output.config(state=tk.DISABLED)

    def _poll_gesture(self) -> None:
        if self.gesture_engine:
            status = self.gesture_engine.get_status()
            if status.get("gesture") != "none":
                self._gesture_append(f"[GESTURE] {status.get('gesture')} ({status.get('confidence')})")
        self.root.after(1000, self._poll_gesture)

    # ------------------------------------------------------------------
    # Vision ROI tab
    # ------------------------------------------------------------------
    def _build_vision_tab(self) -> None:
        frame = self.tab_vision
        frame.configure(bg=BG)

        tk.Label(frame, text="Vision ROI — Dynamic Filters by Hand", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.vision_roi = VisionROI() if VisionROI else None

        self.vision_status_var = tk.StringVar(value="Inactive")
        tk.Label(btn_frame, textvariable=self.vision_status_var, bg=BG, fg=TEXT_DIM, font=FONT).pack(side=tk.RIGHT)

        tk.Button(
            btn_frame, text="Start Camera", command=self._vision_start,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Stop", command=self._vision_stop,
            bg=RED, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Next Filter", command=self._vision_next_filter,
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self.vision_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.vision_output.yview)
        self.vision_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.vision_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        if self.vision_roi:
            self._vision_append("[READY] Vision ROI initialized. Filters: none, ascii, dots, cyan, thermal.")
        else:
            self._vision_append("[ERROR] Vision ROI not available. Install opencv-python and mediapipe.")

        self._poll_vision()

    def _vision_start(self) -> None:
        if not self.vision_roi:
            return
        self.vision_roi.start()
        self.vision_status_var.set("Running")
        self._vision_append("[STARTED] Camera active. Show 4 fingers to define ROI polygon.")

    def _vision_stop(self) -> None:
        if not self.vision_roi:
            return
        self.vision_roi.stop()
        self.vision_status_var.set("Stopped")
        self._vision_append("[STOPPED]")

    def _vision_next_filter(self) -> None:
        if not self.vision_roi:
            return
        self.vision_roi.next_filter()
        self._vision_append(f"[FILTER] {self.vision_roi.current_filter}")

    def _vision_append(self, text: str) -> None:
        self.vision_output.config(state=tk.NORMAL)
        self.vision_output.insert(tk.END, text + "\n")
        self.vision_output.see(tk.END)
        self.vision_output.config(state=tk.DISABLED)

    def _poll_vision(self) -> None:
        if self.vision_roi:
            status = self.vision_roi.get_status()
            if status.get("polygon_points", 0) >= 4:
                self._vision_append(f"[ROI] Active — filter={status.get('filter')}")
        self.root.after(1000, self._poll_vision)

    # ------------------------------------------------------------------
    # OSINT tab
    # ------------------------------------------------------------------
    def _build_osint_tab(self) -> None:
        frame = self.tab_osint
        frame.configure(bg=BG)

        tk.Label(frame, text="OSINT Dashboard", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        self.osint_dash = OSINTDashboard() if OSINTDashboard else None

        cat_frame = tk.Frame(frame, bg=BG)
        cat_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(cat_frame, text="Category:", bg=BG, fg=TEXT, font=FONT).pack(side=tk.LEFT, padx=(0, 8))
        self.osint_cat_var = tk.StringVar(value="people")
        cat_combo = ttk.Combobox(cat_frame, textvariable=self.osint_cat_var, state="readonly")
        cat_combo["values"] = self.osint_dash.list_categories() if self.osint_dash else []
        cat_combo.pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            cat_frame, text="Load Tools", command=self._osint_load_tools,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            cat_frame, text="Generate Identity", command=self._osint_generate_identity,
            bg=YELLOW, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self.osint_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.osint_output.yview)
        self.osint_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.osint_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        if not self.osint_dash:
            self._osint_append("[ERROR] OSINT dashboard not available.")

    def _osint_load_tools(self) -> None:
        if not self.osint_dash:
            return
        cat = self.osint_cat_var.get()
        tools = self.osint_dash.list_tools(cat)
        self._osint_append(f"[{cat.upper()}]")
        for t in tools:
            self._osint_append(f"  - {t['name']}: {t['url']}")

    def _osint_generate_identity(self) -> None:
        if not self.osint_dash:
            return
        identity = self.osint_dash.generate_identity()
        self._osint_append("[IDENTITY]")
        for k, v in identity.items():
            self._osint_append(f"  {k}: {v}")

    def _osint_append(self, text: str) -> None:
        self.osint_output.config(state=tk.NORMAL)
        self.osint_output.insert(tk.END, text + "\n")
        self.osint_output.see(tk.END)
        self.osint_output.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Plugins tab
    # ------------------------------------------------------------------
    def _build_plugins_tab(self) -> None:
        frame = self.tab_plugins
        frame.configure(bg=BG)

        tk.Label(frame, text="Plugin System", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(
            anchor="w", padx=16, pady=12
        )

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Button(
            btn_frame, text="Load Plugins", command=self._plugins_load,
            bg=ACCENT2, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_frame, text="Refresh", command=self._plugins_refresh,
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        self.plugins_output = tk.Text(
            frame, bg=PANEL, fg=TEXT, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT
        )
        scrollbar = ttk.Scrollbar(frame, command=self.plugins_output.yview)
        self.plugins_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.plugins_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self._plugins_load()

    def _plugins_load(self) -> None:
        if not self.plugins:
            self._plugins_append("[ERROR] Plugin system not available.")
            return
        loaded = self.plugins.load_from_directory()
        self.plugins.load_all()
        self._plugins_append(f"[LOADED] {len(loaded)} plugins: {', '.join(loaded) if loaded else 'none'}")
        for plugin in self.plugins.get_all_plugins():
            self._plugins_append(f"  - {plugin.get_name()} v{plugin.get_version()}: {plugin.get_description()}")

    def _plugins_refresh(self) -> None:
        self.plugins_output.config(state=tk.NORMAL)
        self.plugins_output.delete("1.0", tk.END)
        self.plugins_output.config(state=tk.DISABLED)
        self._plugins_load()

    def _plugins_append(self, text: str) -> None:
        self.plugins_output.config(state=tk.NORMAL)
        self.plugins_output.insert(tk.END, text + "\n")
        self.plugins_output.see(tk.END)
        self.plugins_output.config(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # 3D Particles tab
    # ------------------------------------------------------------------
    def _build_particles_tab(self) -> None:
        frame = self.tab_particles
        frame.configure(bg=BG)

        title = tk.Label(frame, text="3D Particle Engine — DOMAIN EXPANSION", font=FONT_JJK_SMALL, bg=BG, fg=ACCENT2)
        title.pack(anchor="w", padx=16, pady=12)
        try:
            from jjk_style import JJKTheme
            JJKTheme.apply_glow(title, JJKTheme.ACCENT2, 3)
        except Exception:
            pass

        info_frame = tk.Frame(frame, bg=BG)
        info_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.particle_status = tk.Label(
            info_frame, text="Status: idle | Energy: 100/100", bg=BG, fg=TEXT, font=FONT_BOLD
        )
        self.particle_status.pack(side=tk.LEFT)

        tk.Button(
            info_frame, text="START", command=self._particles_start,
            bg=ACCENT2, fg="black", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            info_frame, text="STOP", command=self._particles_stop,
            bg=RED, fg="white", font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            info_frame, text="CLEAR", command=self._particles_clear,
            bg=PANEL, fg=TEXT, font=FONT_BOLD, relief=tk.FLAT, padx=12
        ).pack(side=tk.LEFT)

        mode_frame = tk.Frame(frame, bg=BG)
        mode_frame.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Label(mode_frame, text="DOMAIN:", bg=BG, fg=ACCENT2, font=FONT_BOLD).pack(side=tk.LEFT)
        self.particle_mode = tk.StringVar(value="aura")
        modes = [
            ("INFINITE VOID", "open_hand"),
            ("CURSED BURST", "fist"),
            ("STAR RADIATION", "peace"),
            ("HEAVENLY", "heart"),
            ("BLACK FLASH", "swipe"),
        ]
        for label, value in modes:
            tk.Radiobutton(
                mode_frame, text=label, variable=self.particle_mode, value=value,
                bg=BG, fg=TEXT, selectcolor=PANEL, font=FONT
            ).pack(side=tk.LEFT, padx=(8, 0))

        self.particle_output = tk.Text(
            frame, bg=PANEL, fg=ACCENT2, font=FONT_MONO, wrap=tk.WORD, state=tk.DISABLED, relief=tk.FLAT, height=18
        )
        scrollbar = ttk.Scrollbar(frame, command=self.particle_output.yview)
        self.particle_output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.particle_output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.particle_engine = None
        self.particle_renderer = None
        self.domain = None
        self._particle_update_job: Optional[str] = None

    def _particles_start(self) -> None:
        if self.particle_engine is None:
            try:
                from particle_engine_3d import ParticleEngine3D
                self.particle_engine = ParticleEngine3D()
                self.particle_engine.start()
                self.particle_engine.add_frame_callback(self._particles_on_frame)
            except Exception as e:
                self._particles_append(f"[ERROR] Particle engine: {e}")
                return
        if self.particle_renderer is None:
            try:
                from particle_renderer_3d import ParticleRenderer3D
                self.particle_renderer = ParticleRenderer3D()
                self.particle_renderer.start()
            except Exception as e:
                self._particles_append(f"[ERROR] Particle renderer: {e}")
                return
        if self.domain is None:
            try:
                from domain_expansion import DomainExpansion
                self.domain = DomainExpansion(self.particle_engine)
                self.domain.start()
                self.domain.add_callback(self._on_domain_event)
            except Exception as e:
                self._particles_append(f"[ERROR] Domain expansion: {e}")
        self.particle_status.config(text="Status: running")
        self._particles_append("[STARTED] 3D particle engine + Domain Expansion")
        self._particle_update_job = self.root.after(250, self._particles_update_status)

    def _particles_stop(self) -> None:
        if self.particle_engine:
            self.particle_engine.stop()
            self.particle_engine = None
        if self.particle_renderer:
            self.particle_renderer.stop()
            self.particle_renderer = None
        if self._particle_update_job:
            self.root.after_cancel(self._particle_update_job)
            self._particle_update_job = None
        self.particle_status.config(text="Status: idle")
        self._particles_append("[STOPPED] 3D particle engine")

    def _particles_clear(self) -> None:
        if self.particle_engine:
            self.particle_engine.particles = []
        self._particles_append("[CLEARED] Particles")

    def _particles_on_frame(self, particles: list, count: int, gesture: str) -> None:
        if self.particle_renderer:
            try:
                self.particle_renderer.update_particles(particles)
            except Exception:
                pass

    def _particles_update_status(self) -> None:
        if self.particle_engine:
            status = self.particle_engine.get_status()
            self.particle_status.config(
                text=f"Status: {'running' if status['running'] else 'idle'} | Particles: {status['particles']} | Gesture: {status['gesture']}"
            )
            self._particles_update_gesture_source()
        if self.particle_engine and self.particle_engine.running:
            self._particle_update_job = self.root.after(500, self._particles_update_status)

    def _particles_update_gesture_source(self) -> None:
        try:
            gesture = getattr(self, "current_gesture", "none")
            x, y, z = getattr(self, "current_gesture_pos", (0.0, 0.0, 0.0))
            confidence = float(getattr(self, "current_gesture_conf", 0.0))
            if gesture != "none" and confidence > 0.3:
                if self.particle_engine:
                    self.particle_engine.set_gesture(gesture, x, y, z, confidence)
                if self.domain:
                    expanded = self.domain.expand(gesture, x, y, z)
                    if expanded:
                        self._particles_append(f"[DOMAIN] {DOMAINS.get(gesture, DomainConfig('', (0,0,0), (0,0,0))).name}")
        except Exception:
            pass

    def _particles_append(self, text: str) -> None:
        self.particle_output.config(state=tk.NORMAL)
        self.particle_output.insert(tk.END, text + "\n")
        self.particle_output.see(tk.END)
        self.particle_output.config(state=tk.DISABLED)

    def _on_domain_event(self, payload: Dict[str, Any]) -> None:
        try:
            event = payload.get("event")
            if event == "domain_start":
                self._particles_append(f"[DOMAIN EXPANSION] {payload.get('name', '')}")
                if self.particle_renderer:
                    cp = payload.get("color_primary", (0, 0, 0))
                    cs = payload.get("color_secondary", (0, 0, 0))
                    r, g, b = cs
                    self.particle_renderer._domain_color = (r / 255, g / 255, b / 255)
            elif event == "domain_end":
                self._particles_append("[DOMAIN END]")
                if self.particle_renderer:
                    self.particle_renderer._domain_active = False
                    self.particle_renderer._domain_progress = 0.0
            elif event == "tick":
                energy = payload.get("energy", 0)
                max_energy = payload.get("max_energy", 100)
                progress = payload.get("progress", 0)
                active = payload.get("active", False)
                status_text = f"Energy: {energy:.0f}/{max_energy:.0f}"
                if active:
                    status_text += f" | Domain: {payload.get('name', '')} {progress*100:.0f}%"
                self.particle_status.config(text=status_text)
                if self.particle_renderer:
                    self.particle_renderer._domain_active = active
                    self.particle_renderer._domain_progress = progress
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status / misc
    # ------------------------------------------------------------------
    def _log(self, text: str) -> None:
        self.log_queue.put(("app", text))

    def _show_welcome(self) -> None:
        ai_status = "ACTIVE" if self.ai else "UNAVAILABLE"
        plugins_status = "ACTIVE" if self.plugins else "UNAVAILABLE"
        welcome = (
            "Bienvenido a AURA Desktop.\n"
            f"AI Providers: {ai_status} | Plugins: {plugins_status}\n"
            "Chat embebido activo — sin localhost, sin navegador.\n"
            "Comandos: /help, /clear, /status, /stats, /services, /logs, /train\n"
            "Módulos: Voice, Gestures, Vision, OSINT, Repair, Agents, Plugins.\n"
        )
        self._append_chat("bot", welcome)

    def _flush_init_log(self) -> None:
        for line in self._init_log:
            self._repair_append(line)

    def _update_status_periodically(self) -> None:
        try:
            stats = self.embedded.get_stats() if self.embedded else {}
            status = stats.get("status", "active")
            color = GREEN if status == "active" else RED
            ai_info = ""
            if self.ai:
                usage = self.ai.get_usage()
                ai_info = f" | AI requests={usage.get('requests', 0)}"
            status_text = f"● AURA: {status} | messages={stats.get('messages', 0)}{ai_info}"
            self.status_var.set(status_text)
            try:
                self.status_var.config(fg=color)
            except Exception:
                pass
        except Exception:
            self.status_var.set("● AURA: error")
            self.status_var.config(fg=RED)

        # Telemetry update
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0)
            ram = psutil.virtual_memory().percent
            self.cpu_label.config(text=f"CPU: {cpu:.0f}%")
            self.ram_label.config(text=f"RAM: {ram:.0f}%")
        except Exception:
            self.cpu_label.config(text="CPU: N/A")
            self.ram_label.config(text="RAM: N/A")

        # Model info
        try:
            status_resp = self.client.status()
            model = status_resp.get("local_model", "--") if isinstance(status_resp, dict) else "--"
            self.model_label.config(text=f"Model: {model}")
            agents = status_resp.get("agents", 0) if isinstance(status_resp, dict) else 0
            self.agents_label.config(text=f"Agents: {agents}")
        except Exception:
            self.model_label.config(text="Model: N/A")
            self.agents_label.config(text="Agents: N/A")

        # Nucleus status
        if self.nucleus:
            if status == "active":
                self.nucleus.set_status("active")
            elif status == "idle":
                self.nucleus.set_status("warning")
            else:
                self.nucleus.set_status("error")

        self.root.after(3000, self._update_status_periodically)


# ---------------------------------------------------------------------------
# Entrypoints
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="AURA Desktop App")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies then exit")
    args = parser.parse_args()

    if args.install_deps:
        ensure_deps()
        print("Dependencies installed.")
        return 0

    root = tk.Tk()
    app = AuraApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
