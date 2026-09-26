#!/usr/bin/env python3
"""AURA Runner — Núcleo funcional.
Inicia backend mínimo + ventana nativa tkinter (Jarvis/Ultron style).
Silencioso, sin terminal, 100% local.
"""
import os
import sys
import time
import json
import threading
import urllib.request
import queue
import tkinter as tk
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
import uvicorn
from typing import Optional, Any

PROJECT_ROOT = Path(__file__).resolve().parent
AURA_APP_DIR = PROJECT_ROOT / "AURA_APP"

# Mismo orden que AURA_APP/backend/app.py para que los paquetes `backend.*`
# (skills, memory) y ai_providers resuelvan exactamente igual que en el runtime.
for _p in (str(PROJECT_ROOT), str(AURA_APP_DIR), str(AURA_APP_DIR / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PORT = int(os.getenv("AURA_PORT", os.environ.get("PORT", "8000")))

OLLAMA_BASE = os.getenv("LOCAL_LFM_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2")

# 'localhost' puede resolver a ::1 (IPv6) mientras Ollama sólo escucha en
# 127.0.0.1 en algunas instalaciones de Windows -> probamos ambos candidatos.
_OLLAMA_CANDIDATES = [OLLAMA_BASE]
for _alt in ("http://127.0.0.1:11434", "http://localhost:11434"):
    if _alt not in _OLLAMA_CANDIDATES:
        _OLLAMA_CANDIDATES.append(_alt)
_ollama_base_live: Optional[str] = None

app = FastAPI(title="AURA OS Backend", version="2.0.0")


def ollama_base() -> str:
    """Base de Ollama que respondió por última vez (o la configurada)."""
    return _ollama_base_live or OLLAMA_BASE


def ollama_get(path: str, timeout: int = 3) -> Optional[dict]:
    """GET a Ollama probando los candidatos y fijando el que responde."""
    global _ollama_base_live
    for base in _OLLAMA_CANDIDATES:
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=timeout) as r:
                if r.status == 200:
                    _ollama_base_live = base
                    return json.loads(r.read())
        except Exception:
            continue
    return None


def list_ollama_models() -> list:
    """Modelos instalados en Ollama (lista vacía si está offline)."""
    data = ollama_get("/api/tags")
    if not data:
        return []
    return [m.get("name", "") for m in (data.get("models") or []) if m.get("name")]


class HFChatRequest(BaseModel):
    message: str
    history: list = []
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 512
    # Antes faltaba y /api/training/start fallaba con AttributeError (500).
    model_name: str = ""


class ChatRequest(BaseModel):
    message: str


def check_ollama(timeout: int = 3) -> bool:
    data = ollama_get("/api/tags", timeout=timeout)
    return bool(data and data.get("models"))


def ollama_chat(message: str, system_prompt: str = "", history: list = None,
                temperature: float = 0.7, max_tokens: int = 512) -> dict | None:
    if not check_ollama():
        return None
    try:
        start = time.time()
        history = history or []   # antes: `history + [[...]]` reventaba con None (quedaba en None silencioso)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for pair in history:
                if isinstance(pair, list) and len(pair) >= 2:
                    messages.append({"role": "user", "content": str(pair[0])})
                    messages.append({"role": "assistant", "content": str(pair[1])})
        messages.append({"role": "user", "content": message})
        body = json.dumps({
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }).encode()
        req = urllib.request.Request(
            f"{ollama_base()}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("message") or {}).get("content") or "").strip()
        if not text:
            return None
        return {
            "message": text,
            "response": text,
            "history": history + [[message, text]],
            "model": OLLAMA_MODEL,
            "provider": "ollama",
            "latency": int((time.time() - start) * 1000),
            "finish_reason": "completed",
        }
    except Exception:
        return None


@app.get("/")
def index():
    html_path = PROJECT_ROOT / "AURA_APP" / "frontend" / "index.html"
    if html_path.exists():
        return Response(content=html_path.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")
    return Response(content="<html><body>AURA OS</body></html>", media_type="text/html")


@app.get("/health")
def health():
    ollama_ok = check_ollama()
    return {"status": "ok", "mode": "aura-runner", "ollama": ollama_ok, "timestamp": time.time()}


@app.get("/api/status")
def status():
    return {
        "backend": "running",
        "mode": "aura-runner",
        "port": PORT,
        "ollama": check_ollama(),
        "local_model": OLLAMA_MODEL,
    }


@app.get("/api/logs")
def logs(service: str = "backend", lines: int = 100):
    log_path = PROJECT_ROOT / "backend" / "uvicorn.log"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        file_lines = text.strip().split("\n")
        return {"service": service, "lines": file_lines[-lines:]}
    return {"service": service, "lines": [], "note": "no log file"}


@app.post("/api/hf-chat")
def hf_chat(req: HFChatRequest):
    result = ollama_chat(
        message=req.message,
        system_prompt=req.system_prompt,
        history=req.history,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    if result:
        return result
    reply = (
        f"Recibido: '{req.message}'. "
        "Modelo local no disponible — instalá Ollama con `ollama pull dolphin-2_6-phi-2` para IA local."
    )
    return {
        "message": reply,
        "model": "aura-launcher",
        "finish_reason": "completed",
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    hf_req = HFChatRequest(message=req.message)
    return hf_chat(hf_req)


@app.get("/api/training/status")
def training_status():
    return {"status": "idle", "model": None, "progress": 0, "samples": 0}


@app.post("/api/training/start")
def training_start(req: HFChatRequest):
    return {"status": "queued", "model": req.model_name or "unknown"}


@app.get("/api/atria/health")
def atria_health():
    sys.path.insert(0, str(PROJECT_ROOT / "AURA_APP" / "backend"))
    from ai_providers import AIProviderManager
    mgr = AIProviderManager()
    return mgr.get_atria_health()


@app.get("/api/atria/providers")
def atria_providers():
    sys.path.insert(0, str(PROJECT_ROOT / "AURA_APP" / "backend"))
    from ai_providers import AIProviderManager
    mgr = AIProviderManager()
    return {
        "atria_dawn": mgr.providers.get("atria_dawn"),
        "available": mgr.get_available_providers(),
        "best": mgr.get_best_provider(),
    }


class AtriaTaskRequest(BaseModel):
    objective: str
    dimension: str = "general"
    context: str = ""
    max_steps: int = 20


atria_engine: Optional[Any] = None


@app.post("/api/atria/task")
def atria_task(req: AtriaTaskRequest):
    global atria_engine
    if atria_engine is None:
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "AURA_APP" / "backend"))
            from atria_engine import AtriaAgenticEngine
            atria_engine = AtriaAgenticEngine(str(PROJECT_ROOT))
        except Exception as exc:
            return {"error": f"Engine init failed: {exc}"}
    task_id = atria_engine.submit_task(req.objective, req.dimension, req.context, req.max_steps)
    return {"task_id": task_id, "status": "running"}


@app.get("/api/atria/task/{task_id}")
def atria_task_status(task_id: str):
    global atria_engine
    if atria_engine is None:
        return {"error": "Engine not initialized"}
    return atria_engine.get_task_status(task_id)


@app.get("/api/atria/task/{task_id}/result")
def atria_task_result(task_id: str):
    global atria_engine
    if atria_engine is None:
        return {"error": "Engine not initialized"}
    return atria_engine.get_task_result(task_id)


# ---------------------------------------------------------------------------
# IA local — streaming SSE (misma fuente de verdad: ai_providers.py)
# ---------------------------------------------------------------------------
class ChatStreamRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    mode: str = "text"
    history: Optional[list] = None
    system_prompt: Optional[str] = None


_ai_manager = None
_skill_registry = None


def get_ai_manager():
    """AIProviderManager compartido (import perezoso: es pesado al cargar)."""
    global _ai_manager
    if _ai_manager is None:
        from ai_providers import AIProviderManager
        _ai_manager = AIProviderManager()
    return _ai_manager


def get_skill_registry():
    global _skill_registry
    if _skill_registry is None:
        from backend.skills.registry import SkillRegistry
        _skill_registry = SkillRegistry()
    return _skill_registry


def skills_list() -> list:
    try:
        return get_skill_registry().list()
    except Exception:
        return []


@app.post("/api/chat/stream")
def chat_stream(req: ChatStreamRequest):
    """SSE token a token hacia el HUD (conserva los espacios de cada token)."""
    text = (req.message or "").strip()
    history = req.history or []
    system_prompt = req.system_prompt or ""

    def gen():
        if not text:
            yield "data: " + json.dumps({"error": "message vacio"}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
            return
        emitted = False
        try:
            stream = get_ai_manager().chat_stream_ollama(
                text, history=history, system_prompt=system_prompt
            )
            for piece in stream:
                if not piece:
                    continue
                emitted = True
                yield "data: " + json.dumps({"token": piece}, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
        if not emitted:
            yield "data: " + json.dumps({"error": "sin respuesta del modelo local"}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/ollama/status")
def ollama_status():
    """Estado de Ollama local + modelos instalados (re-detectado en vivo)."""
    models = list_ollama_models()
    active = OLLAMA_MODEL
    try:
        info = get_ai_manager().refresh_ollama()
        if isinstance(info, dict) and info:
            return {
                "online": info.get("online", bool(models)),
                "models": info.get("models", models),
                "active": info.get("active", active),
                "installed": info.get("installed", bool(models)),
                "base_url": ollama_base(),
            }
    except Exception:
        pass
    return {
        "online": bool(models),
        "models": models,
        "active": active,
        "installed": bool(models),
        "base_url": ollama_base(),
    }


@app.get("/api/system/status")
def system_status():
    """Mismo contrato que el runtime principal: 'memory' es el % de RAM del HUD."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.expanduser("~")).percent
    except Exception:
        cpu, mem, disk = 0.0, 0.0, 0.0
    return {
        "backend": "running",
        "cpu": cpu,
        "memory": mem,
        "disk": disk,
        "mode": "aura-runner",
        "version": "2.0.0",
        "ollama": check_ollama(),
        "local_model": OLLAMA_MODEL,
        "skills": len(skills_list()),
    }


@app.get("/api/system/health")
def system_health():
    """Salud global para el HUD (mismo contrato que AURA_APP/backend/app.py)."""
    online = check_ollama()
    return {
        "status": "healthy" if online else "degraded",
        "issues": [] if online else ["ollama_offline"],
        "services": {
            "backend": {"state": "running"},
            "ollama": {"state": "up" if online else "down"},
            "skills": {"state": "up", "count": len(skills_list())},
        },
        "jan": None,
        "websocket": {"status": "idle"},
        "mdns_peers": {"count": 0},
        "mobile_sync": {"status": "idle", "nodes": 0},
        "mode": "aura-runner",
        "timestamp": time.time(),
    }


@app.get("/api/skills")
def list_skills():
    skills = skills_list()
    return {"skills": skills, "count": len(skills)}


@app.get("/api/skills/search")
def search_skills(q: str = "", top_k: int = 5):
    q = (q or "").strip()
    if not q:
        return {"query": q, "results": skills_list()[:top_k]}
    try:
        return {"query": q, "results": get_skill_registry().search(q, top_k=top_k)}
    except Exception:
        return {"query": q, "results": []}


@app.post("/api/skills/{skill_name}")
def run_skill(skill_name: str, params: Optional[dict] = None):
    try:
        return get_skill_registry().run(skill_name, params or {})
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# Panel P2P del HUD: se monta el router real de backend/p2p_reconcile.py.
# Si no está disponible se registra un stub con ceros válidos para que el HUD
# no muestre errores de red.
try:
    from backend.p2p_reconcile import router as p2p_reconcile_router
    app.include_router(p2p_reconcile_router)
except Exception as _p2p_exc:
    print(f"[AURA Runner] p2p_reconcile no montado ({_p2p_exc}); usando stub")

    @app.get("/api/sync/reconcile/status")
    def reconcile_status_stub():
        return {
            "status": "ok",
            "last_reconcile": None,
            "last_summary": {},
            "tracked_docs": 0,
            "backups_count": 0,
            "note": "p2p_reconcile no disponible",
        }


def start_backend():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="error")


def _health_urls() -> list:
    """IPv4 primero: 'localhost' puede resolver a ::1 y fallar en Windows."""
    return [f"http://127.0.0.1:{PORT}/health", f"http://localhost:{PORT}/health"]


def backend_alive(timeout: int = 1) -> bool:
    for url in _health_urls():
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                if r.status == 200:
                    return True
        except Exception:
            continue
    return False


def wait_backend(timeout: int = 15) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if backend_alive():
            return True
        time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Splash de arranque: readiness del backend + Ollama, con reintento
# ---------------------------------------------------------------------------
SPLASH_BG = "#05070a"
SPLASH_PANEL = "#0d1117"
SPLASH_ACCENT = "#7c4dff"
SPLASH_CYAN = "#00e5ff"
SPLASH_TEXT = "#e6e9f0"
SPLASH_DIM = "#5c6478"
SPLASH_OK = "#00e676"
SPLASH_ERR = "#ff4d4d"
SPLASH_WARN = "#ffea00"


class SplashWindow:
    """Ventana de arranque: sondea backend y Ollama antes de abrir el núcleo.

    Los sondeos corren en un hilo aparte y se comunican por Queue para no
    congelar la UI (check_ollama puede tardar segundos si Ollama está caído).
    """

    def __init__(self, backend_probe, ollama_probe, min_ms: int = 1200) -> None:
        self.backend_probe = backend_probe
        self.ollama_probe = ollama_probe
        self.min_ms = min_ms
        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self.finished = False
        self.backend_ok = False
        self.ollama_done = False
        self.launch_now = False
        self.started = time.time()

        self.root = tk.Tk()
        self.root.title("AURA OS")
        self.root.overrideredirect(True)
        self.root.configure(bg=SPLASH_BG)
        w, h = 500, 300
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass
        self._build()
        self.root.after(60, self._start_probe)
        self.root.after(120, self._tick)

    # -- construcción ------------------------------------------------------
    def _build(self) -> None:
        wrap = tk.Frame(self.root, bg=SPLASH_BG, highlightthickness=1,
                        highlightbackground="#1b2130")
        wrap.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(wrap, text="AURA", font=("Segoe UI", 30, "bold"),
                 bg=SPLASH_BG, fg=SPLASH_ACCENT).pack(pady=(14, 0))
        tk.Label(wrap, text="O S   ·   N Ú C L E O   v 3", font=("Segoe UI", 9, "bold"),
                 bg=SPLASH_BG, fg=SPLASH_CYAN).pack()

        rows = tk.Frame(wrap, bg=SPLASH_BG)
        rows.pack(fill=tk.X, padx=28, pady=(16, 0))
        self.row_backend = self._row(rows, "Backend")
        self.row_ollama = self._row(rows, "Ollama")
        self.row_model = self._row(rows, "Modelo local")

        self.status_var = tk.StringVar(value="Iniciando el núcleo…")
        tk.Label(wrap, textvariable=self.status_var, font=("Consolas", 8),
                 bg=SPLASH_BG, fg=SPLASH_DIM).pack(pady=(16, 0))

        btns = tk.Frame(wrap, bg=SPLASH_BG)
        btns.pack(pady=(12, 4))
        self.btn_retry = self._button(btns, "Reintentar", self._retry, SPLASH_CYAN)
        self.btn_skip = self._button(btns, "Continuar igualmente", self._skip, SPLASH_DIM)

    def _row(self, parent, title: str):
        row = tk.Frame(parent, bg=SPLASH_BG)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=title, width=13, anchor="w", font=("Consolas", 9),
                 bg=SPLASH_BG, fg=SPLASH_DIM).pack(side=tk.LEFT)
        var = tk.StringVar(value="· esperando")
        lbl = tk.Label(row, textvariable=var, anchor="w", font=("Consolas", 9, "bold"),
                       bg=SPLASH_BG, fg=SPLASH_DIM)
        lbl.pack(side=tk.LEFT)
        return (var, lbl)

    def _button(self, parent, text: str, cmd, fg: str):
        return tk.Button(parent, text=text, command=cmd, bg=SPLASH_PANEL, fg=fg,
                         relief=tk.FLAT, font=("Segoe UI", 9, "bold"), padx=14, pady=6,
                         activebackground="#111820", activeforeground=SPLASH_TEXT,
                         highlightthickness=0, bd=0, cursor="hand2")

    @staticmethod
    def _set(row, text: str, color: str) -> None:
        var, lbl = row
        var.set(text)
        lbl.configure(fg=color)


    # -- ciclo de vida -----------------------------------------------------
    def run(self) -> bool:
        self.root.protocol("WM_DELETE_WINDOW", self._skip)
        self.root.mainloop()
        return self.launch_now

    def _start_probe(self) -> None:
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._probe, daemon=True).start()

    def _probe(self) -> None:
        try:
            self.q.put(("backend", bool(self.backend_probe())))
        except Exception as exc:
            self.q.put(("backend", False))
            self.q.put(("note", f"backend probe: {exc}"))
        try:
            online, models = self.ollama_probe()
            self.q.put(("ollama", (bool(online), list(models or []))))
        except Exception as exc:
            self.q.put(("ollama", (False, [])))
            self.q.put(("note", f"ollama probe: {exc}"))

    def _tick(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                self._apply(kind, payload)
        except queue.Empty:
            pass
        if not self.finished:
            self.root.after(150, self._tick)

    # -- reacciones --------------------------------------------------------
    def _apply(self, kind: str, payload) -> None:
        if kind == "backend":
            self.busy = False
            if payload:
                self.backend_ok = True
                self._set(self.row_backend, "● activo", SPLASH_OK)
            else:
                self._set(self.row_backend, "● sin respuesta", SPLASH_ERR)
                self.status_var.set("El backend no responde — reintentá o continuá igual")
                self.btn_retry.pack(side=tk.LEFT, padx=4)
                self.btn_skip.pack(side=tk.LEFT, padx=4)
        elif kind == "ollama":
            self.ollama_done = True
            online, models = payload
            if online:
                self._set(self.row_ollama, "● online", SPLASH_OK)
                base = OLLAMA_MODEL.split(":")[0]
                if models and not any(str(m).split(":")[0] == base for m in models):
                    self._set(self.row_model, f"⚠ {OLLAMA_MODEL} no instalado", SPLASH_WARN)
                    self.status_var.set(f"Falta el modelo: ollama pull {OLLAMA_MODEL}")
                else:
                    self._set(self.row_model, OLLAMA_MODEL, SPLASH_OK)
            else:
                self._set(self.row_ollama, "○ offline", SPLASH_WARN)
                self._set(self.row_model, f"— ollama pull {OLLAMA_MODEL}", SPLASH_WARN)
                self.status_var.set("IA local no disponible — AURA arranca igual")
            self._maybe_finish()
        elif kind == "note":
            sys.stderr.write(f"[splash] {payload}\n")

    def _maybe_finish(self) -> None:
        if self.finished or not (self.backend_ok and self.ollama_done):
            return
        elapsed = (time.time() - self.started) * 1000
        wait = max(0, int(self.min_ms - elapsed))
        self.finished = True
        self.status_var.set("Abriendo el núcleo…")
        self.root.after(wait + 250, self._finish)

    def _finish(self) -> None:
        self.launch_now = True
        for action in (self.root.quit, self.root.destroy):
            try:
                action()
            except Exception:
                pass

    def _retry(self) -> None:
        self.btn_retry.pack_forget()
        self.btn_skip.pack_forget()
        self._set(self.row_backend, "· esperando", SPLASH_DIM)
        self.root.after(50, self._start_probe)

    def _skip(self) -> None:
        self._finish()


def main():
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    sys.path.insert(0, str(PROJECT_ROOT))
    os.chdir(str(PROJECT_ROOT))

    def launch() -> None:
        import aura_app
        aura_app.main()

    splash = SplashWindow(
        backend_probe=lambda: wait_backend(timeout=20),
        ollama_probe=lambda: (check_ollama(timeout=2), list_ollama_models()),
    )
    if not splash.run():
        return
    if not backend_alive():
        sys.stderr.write("WARNING: backend no responde, arrancando de todos modos\n")
    launch()


if __name__ == "__main__":
    main()
