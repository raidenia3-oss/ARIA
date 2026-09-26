"""
AURA Backend main entrypoint.
Exposes WebSocket bridge, AI-powered chat endpoint, telemetry and resilience features.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from automation.self_healing import SelfHealingDaemon
from automation.task_manager import TaskManager
from database.database import Database
from services.ai_engine import AIEngine
from api.api_service import app as telemetry_app

logger = logging.getLogger(__name__)

app = FastAPI(title="AURA Backend")
ai = AIEngine()
task_mgr = TaskManager()
db = Database()

healer = SelfHealingDaemon(task_manager=task_mgr)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount telemetry API under /api prefix
app.mount("/api", telemetry_app)

# Mount dashboard_ui static files at root
dashboard_path = Path(__file__).resolve().parent.parent.parent / "dashboard_ui"
if dashboard_path.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_path), html=True), name="dashboard")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ai": ai.health_check()}


@app.post("/api/chat")
def chat(payload: dict) -> dict:
    prompt = payload.get("prompt", "")
    context = payload.get("context")
    result = ai.chat(prompt=prompt, context=context)
    text = result.get("text", "")
    intent = result.get("intent")
    if intent and intent.get("action") == "START_BOT":
        start_url = payload.get("start_url", "https://example.com/survey")
        status = task_mgr.start_survey_bot(start_url)
        healer.record_activity("surveys", url=start_url)
        return {
            "reply": text or "Bot de encuestas iniciado.",
            "intent": intent,
            "task_status": status,
        }
    return {"reply": text, "provider": result.get("provider")}


@app.websocket("/ws/bridge")
async def ws_bridge(ws: WebSocket) -> None:
    await ws.accept()
    queue: asyncio.Queue[str] = asyncio.Queue()
    shutdown = False

    async def reader() -> None:
        nonlocal shutdown
        while not shutdown:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "chat":
                prompt = msg.get("prompt", "")
                context = msg.get("context")
                result = ai.chat(prompt=prompt, context=context)
                text = result.get("text", "")
                intent = result.get("intent")
                if intent and intent.get("action") == "START_BOT":
                    start_url = "https://example.com/survey"
                    status = task_mgr.start_survey_bot(start_url)
                    healer.record_activity("surveys", url=start_url)
                    await ws.send_text(
                        json.dumps(
                            {"type": "chat", "reply": text or "Iniciando bot...", "task": status}
                        )
                    )
                else:
                    await ws.send_text(
                        json.dumps(
                            {"type": "chat", "reply": text, "provider": result.get("provider")}
                        )
                    )
            elif msg.get("type") == "task_stop":
                task_mgr.stop_survey_bot()

    async def writer() -> None:
        nonlocal shutdown
        while not shutdown:
            item = await queue.get()
            await ws.send_text(item)

    reader_task = asyncio.create_task(reader())
    writer_task = asyncio.create_task(writer())

    def emit_log(payload: str) -> None:
        try:
            queue.put_nowait(payload)
        except Exception:
            pass

    loop = asyncio.get_event_loop()
    original_run_survey = getattr(task_mgr._solver, "solve_survey", None)

    async def patched_run_survey(start_url: str) -> None:
        setattr(task_mgr._solver, "_on_event", emit_log)
        healer.record_activity("surveys", url=start_url)
        if original_run_survey:
            await original_run_survey(start_url)

    setattr(task_mgr._solver, "solve_survey", patched_run_survey)

    try:
        while True:
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        pass
    finally:
        shutdown = True
        reader_task.cancel()
        writer_task.cancel()
        try:
            await reader_task
        except Exception:
            pass
        try:
            await writer_task
        except Exception:
            pass


@app.post("/emergency")
def emergency() -> dict:
    return {"status": "shutdown_initiated"}


# ------------------------------------------------------------------ #
# Ciclo de vida / resiliencia
# ------------------------------------------------------------------ #

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("AURA Backend starting up")
    await healer.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("AURA Backend shutting down")
    await healer.stop()
    try:
        now_iso = datetime.now().isoformat()
        saved = db.read("data/db.json", default={})
        saved["bots"] = [
            {"id": "bot-1", "name": "Roller Miner", "status": "Idle"},
            {"id": "bot-2", "name": "Survey Harvester", "status": "Stopped"},
            {"id": "bot-3", "name": "OSINT Recon", "status": "Stopped"},
        ]
        saved.setdefault("logs", []).append(
            {"ts": now_iso, "level": "INFO", "message": "Servidor apagado correctamente (graceful shutdown)"}
        )
        db.write("data/db.json", saved)
    except Exception as exc:
        logger.error("Error guardando estado final: %s", exc)

    try:
        task_mgr.stop_survey_bot()
    except Exception as exc:
        logger.error("Error deteniendo tareas al apagar: %s", exc)


def _handle_exit(signum: int, frame: Any) -> None:
    logger.info("Señal de terminación recibida (%s)", signum)
    sys.stderr.write(f"Recibida señal {signum}. Apagando gracefully...\n")
    try:
        task_mgr.stop_survey_bot()
    except Exception as exc:
        logger.error("Error en handler de señal: %s", exc)


for _sig in (signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, _handle_exit)
    except Exception as exc:
        logger.debug("No se pudo registrar handler para %s: %s", _sig, exc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)