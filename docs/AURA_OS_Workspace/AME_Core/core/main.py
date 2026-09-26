#!/usr/bin/env python3
"""AURA Orchestrator v4.0 — SystemDaemon + WebFactory + OmniBar + OCR WS."""

import sys, os, json, asyncio, threading, time, socket, subprocess as sp, re
import logging  # Importar logging
from pathlib import Path
from dotenv import load_dotenv
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, status
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

# Configuración de logging global
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


from automation.rollercoin_bot import _engine
from core.system_daemon import _system_daemon
from core.morph_engine import upscale_image, remove_obstacles, generate_depth_layers
from core.ai_connector import get_prompt, execute_tool
from core.proxy_chat_connector import (
    ProxyChatMessage as ChatMessage,
    stream_proxy_chat as stream_chat_endpoint,
)
from core.forensics_service import (
    MobSFBridge,
    extract_exif,
    format_gps_for_map,
    generate_frida_script,
    run_jadx,
    full_memory_analysis,
)

ADB = r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe"
BASE = Path(__file__).resolve().parent.parent
WEB_VAULT = BASE / "web_vault" / "generated"
WEB_VAULT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AURA Orchestrator v4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── WS Broadcaster ─────────────────────────────────────────────
class WSBroadcaster:
    def __init__(self):
        self._clients: set = set()
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, data: dict):
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        with self._lock:
            for ws in dead:
                self._clients.discard(ws)


wsb = WSBroadcaster()


# ─── Web Factory Engine ─────────────────────────────────────────
class WebFactoryEngine:
    CYBERPUNK_CSS = """*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#00ff88;font-family:'Courier New',monospace;overflow-x:hidden}
.hero{min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#0a0a0f 0%,#1a0033 50%,#0a0a0f 100%);
  position:relative;text-align:center}
.hero::before{content:'';position:absolute;top:0;left:0;right:0;bottom:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,136,0.03) 2px,rgba(0,255,136,0.03) 4px);
  pointer-events:none}
.hero h1{font-size:3rem;text-shadow:0 0 20px #00ff88,0 0 40px #00ff88;margin-bottom:1rem}
.hero p{font-size:1.2rem;color:#88ffcc;max-width:600px;margin:0 auto}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;
  padding:40px 20px;max-width:1200px;margin:0 auto}
.stat-card{background:rgba(0,255,136,0.05);border:1px solid #00ff88;border-radius:8px;
  padding:24px;text-align:center;transition:all 0.3s}
.stat-card:hover{box-shadow:0 0 20px rgba(0,255,136,0.3);transform:translateY(-4px)}
.stat-card h3{color:#00ff88;font-size:2rem;margin-bottom:8px}
.stat-card p{color:#88ffcc;font-size:0.9rem}
.cta{display:block;width:fit-content;margin:40px auto;padding:16px 48px;
  background:#00ff88;color:#0a0a0f;text-decoration:none;font-weight:bold;
  font-size:1.1rem;border-radius:4px;transition:all 0.3s;text-transform:uppercase}
.cta:hover{background:#00cc6a;box-shadow:0 0 30px rgba(0,255,136,0.5)}
footer{text-align:center;padding:40px;color:#444;font-size:0.8rem;border-top:1px solid #1a1a2e}
.particles{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:-1}
.particle{position:absolute;width:2px;height:2px;background:#00ff88;border-radius:50%;
  animation:float linear infinite;opacity:0.4}
@keyframes float{0%{transform:translateY(100vh) rotate(0deg);opacity:0}
  50%{opacity:0.4}100%{transform:translateY(-100px) rotate(720deg);opacity:0}}
"""

    CYBERPUNK_JS = """function createParticles(){const c=document.querySelector('.particles');
if(!c)return;for(let i=0;i<30;i++){const p=document.createElement('div');
p.className='particle';p.style.left=Math.random()*100+'%';
p.style.animationDuration=(5+Math.random()*10)+'s';
p.style.animationDelay=Math.random()*10+'s';c.appendChild(p)}}
document.addEventListener('DOMContentLoaded',createParticles);"""

    def build_page(self, title: str, body_html: str, slug: str) -> dict:
        slug = re.sub(r"[^a-z0-9-]", "-", slug.lower().strip())
        slug = re.sub(r"-+", "-", slug).strip("-") or "page"
        html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{self.CYBERPUNK_CSS}</style></head>
<body><div class="particles"></div><div class="hero"><div><h1>{title}</h1>
<p>{body_html}</p></div></div>
<footer>AURA Web Factory &copy; 2026 — Generado automáticamente</footer>
<script>{self.CYBERPUNK_JS}</script></body></html>"""
        out_dir = WEB_VAULT / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        return {"slug": slug, "path": str(out_dir), "url": f"/webflux/{slug}/"}


_factory = WebFactoryEngine()


# ─── Daemons con broadcast ──────────────────────────────────────
class TelemetryDaemon:
    def __init__(self):
        self._running = threading.Event()
        self._th = None

    async def _loop(self):
        import psutil

        while self._running.is_set():
            try:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                procs = {}
                for pat in ["emulator", "java", "adb", "python", "node", "gradle"]:
                    for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
                        try:
                            if pat in p.info["name"].lower():
                                procs[p.info["pid"]] = {
                                    "n": p.info["name"],
                                    "r": p.info["memory_percent"],
                                    "c": p.info["cpu_percent"],
                                }
                        except Exception:
                            pass
                ports = {}
                for pn, nm in [(5000, "FastAPI"), (5555, "ADB"), (11434, "Ollama")]:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    ports[nm] = s.connect_ex(("127.0.0.1", pn)) == 0
                    s.close()
                try:
                    adb = (
                        "device"
                        in sp.run(
                            [ADB, "devices"], capture_output=True, text=True, timeout=5
                        ).stdout
                    )
                except Exception:
                    adb = False
                payload = {
                    "type": "telemetry",
                    "cpu": cpu,
                    "ram": mem.percent,
                    "ram_gb": round(mem.used / 1e9, 1),
                    "ram_total": round(mem.total / 1e9, 1),
                    "disk": psutil.disk_usage("/").percent,
                    "adb": adb,
                    "ports": ports,
                    "procs": len(procs),
                    "ts": time.time(),
                }
                await wsb.broadcast(payload)
            except Exception:
                pass
            await asyncio.sleep(5)

    def start(self):
        if not self._running.is_set():
            self._running.set()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._th = threading.Thread(
                target=lambda: loop.run_until_complete(self._loop()), daemon=True
            )
            self._th.start()


class ClipboardDaemon:
    def __init__(self):
        self._running = threading.Event()
        self._th = None
        self._last = ""

    async def _loop(self):
        while self._running.is_set():
            try:
                r = sp.run(
                    [ADB, "shell", "service", "call", "clipboard", "1"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.stdout and r.stdout != self._last:
                    self._last = r.stdout
                    await wsb.broadcast(
                        {"type": "clipboard", "data": r.stdout[:200], "ts": time.time()}
                    )
            except Exception:
                pass
            await asyncio.sleep(2)

    def start(self):
        if not self._running.is_set():
            self._running.set()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._th = threading.Thread(
                target=lambda: loop.run_until_complete(self._loop()), daemon=True
            )
            self._th.start()


# Iniciar daemons al importar
td = TelemetryDaemon()
cd = ClipboardDaemon()
td.start()
cd.start()
_system_daemon.set_broadcaster(lambda data: wsb.broadcast(data))
_system_daemon.start()


# ─── WS Endpoints ──────────────────────────────────────────────
@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await wsb.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await wsb.disconnect(ws)


@app.websocket("/ws/rollercoin")
async def ws_rollercoin(ws: WebSocket):
    await wsb.connect(ws)
    _engine.set_ws_broadcaster(wsb.broadcast)
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action", "")
            if action == "start":
                _engine.start_engine()
            elif action == "stop":
                _engine.stop_engine()
            await wsb.broadcast({"type": "rollercoin_cmd", "action": action, "ts": time.time()})
    except WebSocketDisconnect:
        await wsb.disconnect(ws)


@app.websocket("/ws/omnibar")
async def ws_omnibar(ws: WebSocket):
    await wsb.connect(ws)
    try:
        while True:
            data = await ws.receive_json()
            cmd = data.get("command", "").strip().lower()
            result = await _process_omnibar(cmd)
            await ws.send_json(result)
            await wsb.broadcast(
                {"type": "omnibar_result", "cmd": cmd, "result": result, "ts": time.time()}
            )
    except WebSocketDisconnect:
        await wsb.disconnect(ws)


async def _process_omnibar(cmd: str) -> dict:
    if cmd == "/bot start":
        _engine.start_engine()
        return {"ok": True, "msg": "RollercoinBot iniciado", "action": "bot_start"}
    elif cmd == "/bot stop":
        _engine.stop_engine()
        return {"ok": True, "msg": "RollercoinBot detenido", "action": "bot_stop"}
    elif cmd == "/sys stats":
        import psutil

        return {
            "ok": True,
            "action": "sys_stats",
            "cpu": psutil.cpu_percent(interval=0.5),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
        }
    elif cmd.startswith("/web build:"):
        topic = cmd.split(":", 1)[1].strip()
        result = _factory.build_page(
            title=topic.title(),
            body_html=f"Contenido generado automáticamente sobre <strong>{topic}</strong>. "
            f"Motor de generación SEO por AURA Web Factory.",
            slug=topic,
        )
        return {"ok": True, "action": "web_build", **result}
    elif cmd == "/daemon status":
        return {"ok": True, "action": "daemon_status", **_system_daemon.get_telemetry()}
    else:
        return {"ok": False, "msg": f"Comando no reconocido: {cmd}"}


# ─── REST Endpoints ────────────────────────────────────────────
@app.post("/api/v1/rollercoin/start")
async def r_start():
    if _engine.state.get("running"):
        return {"status": "ALREADY_RUNNING"}
    _engine.start_engine()
    await wsb.broadcast({"type": "rollercoin", "status": "STARTING"})
    return {"status": "STARTING"}


@app.post("/api/v1/rollercoin/stop")
async def r_stop():
    _engine.stop_engine()
    await wsb.broadcast({"type": "rollercoin", "status": "STOPPED"})
    return {"status": "STOPPED"}


@app.get("/api/v1/rollercoin/status")
async def r_status():
    s = _engine.state.copy()
    try:
        s["adb"] = (
            "device" in sp.run([ADB, "devices"], capture_output=True, text=True, timeout=5).stdout
        )
    except Exception:
        s["adb"] = False
    return JSONResponse(content=s)


@app.get("/api/v1/rollercoin/dashboard")
async def r_dash():
    s = _engine.state
    return {
        "status": s.get("status", "IDLE"),
        "games_played": s.get("games_played", 0),
        "games_won": s.get("games_won", 0),
        "total_power": s.get("total_power", 0),
        "last_game": s.get("last_game"),
        "last_reward": s.get("last_reward"),
        "running": s.get("running", False),
        "errors": s.get("errors", 0),
        "ocr_balance": s.get("ocr_balance", "N/A"),
        "ocr_power": s.get("ocr_power", "N/A"),
        "ocr_last_text": s.get("ocr_last_text", ""),
    }


@app.post("/api/v1/webfactory/build")
async def webfactory_build(request: Request):
    body = await request.json()
    title = body.get("title", "AURA Generated Page")
    topic = body.get("topic", body.get("query", "crypto"))
    slug = body.get("slug", topic)
    extra_html = body.get("content", "")
    body_html = f"Contenido optimizado SEO sobre <strong>{topic}</strong>."
    if extra_html:
        body_html += f"<br><br>{extra_html}"
    body_html += '<br><br><a class="cta" href="#">Descubre más sobre ' f"{topic}</a>"
    result = _factory.build_page(title=title, body_html=body_html, slug=slug)
    await wsb.broadcast({"type": "webfactory", "result": result, "ts": time.time()})
    return result


@app.get("/api/v1/daemon/telemetry")
async def daemon_telemetry():
    return _system_daemon.get_telemetry()


@app.post("/api/v1/omnibar/command")
async def omnibar_command(request: Request):
    body = await request.json()
    cmd = body.get("command", "").strip().lower()
    result = await _process_omnibar(cmd)
    await wsb.broadcast({"type": "omnibar_result", "cmd": cmd, "result": result, "ts": time.time()})
    return result


@app.post("/api/v1/wallpaper/process")
async def wallpaper_process(request: Request):
    import base64

    body = await request.json()
    mode = body.get("mode", "upscale")
    img_b64 = body.get("image_base64", "")
    if not img_b64:
        return JSONResponse(status_code=400, content={"error": "image_base64 requerido"})
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Base64 inválido"})
    try:
        if mode == "upscale":
            result_bytes = await upscale_image(img_bytes)
            result_b64 = base64.b64encode(result_bytes).decode()
            return {"ok": True, "mode": "upscale", "image_base64": result_b64}
        elif mode == "remove_obstacles":
            region = body.get("region")
            if region and isinstance(region, list) and len(region) == 4:
                region = tuple(region)
            else:
                region = None
            result_bytes = await remove_obstacles(img_bytes, region)
            result_b64 = base64.b64encode(result_bytes).decode()
            return {"ok": True, "mode": "remove_obstacles", "image_base64": result_b64}
        elif mode == "depth":
            depth = await generate_depth_layers(img_bytes)
            subject_b64 = base64.b64encode(depth["subject_png"]).decode()
            bg_b64 = base64.b64encode(depth["background_png"]).decode()
            return {
                "ok": True,
                "mode": "depth",
                "subject_base64": subject_b64,
                "background_base64": bg_b64,
                "width": depth["width"],
                "height": depth["height"],
            }
        else:
            return JSONResponse(status_code=400, content={"error": f"Modo desconocido: {mode}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── GBrain Chat Endpoint (Streaming SSE) ────────────────────────────────────────────
# ─── FORENSICS & REVERSE ENGINEERING ENDPOINTS ─────────────────────


@app.post("/api/v1/forensics/exif")
async def forensics_exif(request: Request):
    """Extraer metadatos EXIF de un archivo de imagen."""
    try:
        body = await request.json()
        import base64

        img_b64 = body.get("image_base64", "")
        filename = body.get("filename", "image.jpg")
        if not img_b64:
            return JSONResponse(status_code=400, content={"error": "image_base64 requerido"})
        img_bytes = base64.b64decode(img_b64)
        result = extract_exif(img_bytes, filename)
        # Si hay GPS, formatear para mapa
        if result.get("gps"):
            result["gps_coordinates"] = format_gps_for_map(result["gps"])
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.post("/api/v1/forensics/memory-analysis")
async def forensics_memory(request: Request):
    """Analizar volcado de memoria RAM con Volatility 3."""
    try:
        body = await request.json()
        filepath = body.get("filepath", "")
        if not filepath:
            return JSONResponse(status_code=400, content={"error": "filepath requerido"})
        result = await full_memory_analysis(filepath)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.post("/api/v1/forensics/mobsf/upload")
async def forensics_mobsf_upload(request: Request):
    """Subir APK a MobSF para análisis."""
    try:
        body = await request.json()
        apk_path = body.get("apk_path", "")
        if not apk_path:
            return JSONResponse(status_code=400, content={"error": "apk_path requerido"})
        result = await MobSFBridge.upload_apk(apk_path)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.post("/api/v1/forensics/mobsf/scan")
async def forensics_mobsf_scan(request: Request):
    """Iniciar escaneo en MobSF."""
    try:
        body = await request.json()
        file_hash = body.get("hash", "")
        scan_type = body.get("scan_type", "static")
        if not file_hash:
            return JSONResponse(status_code=400, content={"error": "hash requerido"})
        result = await MobSFBridge.start_scan(file_hash, scan_type)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.get("/api/v1/forensics/mobsf/report/{file_hash}")
async def forensics_mobsf_report(file_hash: str):
    """Obtener reporte JSON de MobSF."""
    try:
        result = await MobSFBridge.get_report(file_hash)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.get("/api/v1/forensics/mobsf/health")
async def forensics_mobsf_health():
    """Verificar si MobSF está corriendo."""
    result = await MobSFBridge.health_check()
    return result


@app.post("/api/v1/forensics/frida/generate")
async def forensics_frida_generate(request: Request):
    """Generar script de Frida para hooking."""
    try:
        body = await request.json()
        package = body.get("package", "com.ame.ecosystem")
        script_path = generate_frida_script(package=package)
        return {"status": "ok", "script_path": script_path}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


@app.post("/api/v1/forensics/jadx/decompile")
async def forensics_jadx_decompile(request: Request):
    """Descompilar APK con JADX."""
    try:
        body = await request.json()
        apk_path = body.get("apk_path", "")
        if not apk_path:
            return JSONResponse(status_code=400, content={"error": "apk_path requerido"})
        result = run_jadx(apk_path)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)[:300]})


# ─── CYBER-HUD ENDPOINT ────────────────────────────────────────────


@app.get("/hud")
async def cyberpunk_hud():
    """Servir el nuevo AURA CYBER-HUD v5.0 (Cyberpunk/Sci-Fi UI)."""
    from fastapi.responses import HTMLResponse

    hud_path = (
        Path(__file__).resolve().parent.parent
        / "AME_Core"
        / "templates"
        / "aura_cyberpunk_hud.html"
    )
    if hud_path.exists():
        html = hud_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    return HTMLResponse(content="<h1>HUD template not found</h1>", status_code=404)


# ─── LEGACY: GBRAIN HEALTH ──────────────────────────────────────────


@app.get("/api/v1/gbrain/health")
async def gbrain_health():
    """Verifica si el conector de Proxy de IA está configurado correctamente."""
    from core.proxy_chat_connector import health_check

    return await health_check()


@app.post("/api/v1/gbrain/chat/stream")
async def gbrain_chat_stream(request: Request):
    """Endpoint para streaming de chat con HuggingFace Spaces.
    Retorna SSE con eventos de tokens generados por el modelo."""
    try:
        body = await request.json()
        messages = [
            ChatMessage(role=m["role"], content=m["content"]) for m in body.get("messages", [])
        ]

        async def event_stream():
            async for token in stream_chat_endpoint(messages):
                yield f"data: {token}\n\n"

        return StreamingResponse(
            event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Error en el procesamiento: {str(e)}"},
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)
