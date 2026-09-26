"""
Chat routes de AURA — Comandos y endpoints de control
"""
import asyncio
import subprocess
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from backend.daemon.aura_daemon import get_daemon
from backend.agents.learning_agent_fanfic import write_fanfic_with_context
from backend.agents.learning_agent_general import GeneralLearningAgent

router = APIRouter()
command_router = router

@router.post("/command")
async def execute_aura_command(command: str, args: dict = None):
    """Ejecuta comandos directos de AURA"""
    try:
        daemon = get_daemon()
        args = args or {}

        if command == "open_android_studio":
            path = args.get("project", "")
            subprocess.Popen(["C:\\Program Files\\Android\\Android Studio\\bin\\studio64.exe"])
            result = f"Android Studio abierto{f': {path}' if path else ''}"

        elif command == "open_godot":
            subprocess.Popen(["godot"])
            result = "Godot abierto"

        elif command == "open_vscode":
            subprocess.Popen(["C:\\Users\\User\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"])
            result = "VS Code abierto"

        elif command == "write_fanfic":
            prompt = args.get("prompt", "")
            fanfic = await write_fanfic_with_context(prompt)
            result = fanfic if fanfic else "No se pudo generar la fanfic"

        elif command == "learn_papers":
            agent = GeneralLearningAgent()
            insights = await agent.learn_from_arxiv()
            result = f"Aprendido de arxiv: {insights.get('papers_analyzed', 0)} papers"

        elif command == "learn_news":
            agent = GeneralLearningAgent()
            insights = await agent.learn_from_news()
            result = f"Aprendido de noticias: {insights.get('stories_analyzed', 0)} stories"

        elif command == "pause":
            daemon.pause_flag = True
            result = "Daemon pausado"

        elif command == "resume":
            daemon.pause_flag = False
            result = "Daemon reanudado"

        else:
            result = f"Comando '{command}' no reconocido"

        daemon.event_bus.emit_simple("aura_command", {
            "command": command, "result": result,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "command": command,
            "result": result,
            "success": True,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/resources")
async def get_resources():
    """Recursos del sistema en tiempo real"""
    try:
        from backend.daemon.resource_monitor import get_all_resources
        res = get_all_resources()
        return {
            "cpu": res.get("cpu_percent", 0),
            "ram": res.get("ram_percent", 0),
            "disk": res.get("disk_percent", 0),
            "timestamp": datetime.now().isoformat()
        }
    except Exception:
        return {"cpu": 0, "ram": 0, "disk": 0, "timestamp": datetime.now().isoformat()}