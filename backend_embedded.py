"""AURA embedded backend — runnable inside the desktop app without HTTP."""

from __future__ import annotations

import json
import os
import platform
import random
import time
from typing import Any, Dict, List, Optional


class EmbeddedAuraBackend:
    def __init__(self, root: str | None = None) -> None:
        self.root = root or os.getcwd()
        self.history: List[List[str]] = []
        self.system_prompt = os.getenv("AURA_SYSTEM_PROMPT", "Eres AURA, un asistente de IA avanzado.")
        self.temperature = 0.7
        self.max_tokens = 512
        self.start_time = time.time()
        self.message_count = 0
        self.commands_executed: List[Dict[str, Any]] = []

    def chat(self, message: str) -> Dict[str, Any]:
        self.message_count += 1
        text = self._local_response(message)
        entry = [message, text]
        self.history.append(entry)
        if len(self.history) > 200:
            self.history.pop(0)
        return {"message": text, "history": self.history, "count": self.message_count}

    def _local_response(self, message: str) -> str:
        msg = message.strip()
        if not msg:
            return ""
        lower = msg.lower()
        if any(g in lower for g in ["hola", "buenas", "hello", "hi", "qué tal", "buenos días"]):
            return "Hola, soy AURA. ¿En qué puedo ayudarte?"
        if any(g in lower for g in ["como estas", "cómo estás", "como andas", "qué pasa"]):
            return "Estoy operativo. Listo para ayudarte con el proyecto AURA."
        if any(g in lower for g in ["proyecto", "aura"]):
            return "AURA es un ecosistema multi-servicio: backend FastAPI, frontend Next.js, bot Discord, HF Space y app de escritorio."
        if any(g in lower for g in ["backend", "fastapi", "api"]):
            return "El backend corre en el puerto 8000. Endpoints principales: /health, /api/hf-chat, /api/status, /api/logs."
        if any(g in lower for g in ["frontend", "next", "react"]):
            return "El frontend es Next.js en el puerto 3000. Incluye chat, panel de control y tabs de servicios."
        if any(g in lower for g in ["docker", "compose"]):
            return "Podés levantar todo con docker-compose up --build. O usar la app de escritorio aura_app.py."
        if any(g in lower for g in ["error", "falla", "problema", "arreglar"]):
            return "Usá la pestaña Repair de la app de escritorio para escanear y reparar automáticamente el proyecto."
        if any(g in lower for g in ["agente", "agent", "kilo", "cline"]):
            return "La pestaña Agents integra Kilo y Cline. Podés pedirles que escaneen y arreglen errores del proyecto."
        if any(g in lower for g in ["desplegar", "deploy", "producción"]):
            return "Para producción usá docker-compose up --build. AURA soporta PostgreSQL y Redis en producción."
        if any(g in lower for g in ["voz", "voice", "microfono", "micrófono"]):
            return "La pestaña Voice usa wake-word 'hey aura', STT y TTS. Requiere SpeechRecognition y pyttsx3."
        if any(g in lower for g in ["gestos", "gesture", "mano", "cámara"]):
            return "La pestaña Gestures usa MediaPipe para tracking de manos. Clasifica: fist, index, peace, open_hand."
        if any(g in lower for g in ["visión", "vision", "roi", "filtros"]):
            return "La pestaña Vision aplica filtros dinámicos dentro de un polígono definido por tu mano: cyan, thermal, ascii, dots, pixelate, edge."
        if any(g in lower for g in ["osint", "investigación", "busqueda"]):
            return "La pestaña OSINT incluye directorio de herramientas y generador de identidades sintéticas para testing."
        if any(g in lower for g in ["entrenar", "train", "modelo"]):
            return "Entrenamiento disponible en la pestaña Training. Modelo por defecto: Qwen/Qwen2.5-1.5B-Instruct"
        if any(g in lower for g in ["logs", "registros", "bitácora"]):
            return "Logs disponibles en la pestaña Logs. Podés ver logs del backend y servicios."
        if any(g in lower for g in ["status", "estado", "salud"]):
            return self._status_text()
        if "help" in lower or "ayuda" in lower:
            return self._help_text()
        if "/clear" in lower or "limpiar" in lower:
            self.history.clear()
            return "Historial limpiado."
        if "/stats" in lower or "estadísticas" in lower:
            return self._stats_text()
        return f"Recibido: {msg}. Por ahora funciono en modo local. Configurá GEMINI_API_KEY, GROQ_API_KEY u Ollama para respuestas más avanzadas."

    def _status_text(self) -> str:
        uptime = int(time.time() - self.start_time)
        return f"Sistema activo. Uptime: {uptime}s. Mensajes: {self.message_count}. Módulos: Voice, Gestures, Vision, OSINT."

    def _stats_text(self) -> str:
        return f"Mensajes enviados: {self.message_count}. Historial: {len(self.history)} entradas. Tiempo activo: {int(time.time() - self.start_time)}s."

    def _help_text(self) -> str:
        return (
            "Comandos disponibles:\n"
            "- /help — esta ayuda\n"
            "- /clear — limpiar historial\n"
            "- /stats — estadísticas\n"
            "- /status — estado del sistema\n"
            "- /services — lista de servicios\n"
            "- /logs — ver logs\n"
            "- /train — info de entrenamiento\n"
            "También podés preguntar por: voz, gestos, visión, OSINT, deploy, Docker, etc."
        )

    def reset(self) -> None:
        self.history.clear()
        self.commands_executed.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "messages": self.message_count,
            "history_size": len(self.history),
            "status": "active",
            "mode": "embedded",
            "uptime": int(time.time() - self.start_time),
            "platform": platform.system(),
        }

    def execute_system_command(self, command: str) -> Dict[str, Any]:
        self.commands_executed.append({
            "timestamp": time.time(),
            "command": command,
        })
        return {"status": "ok", "command": command, "executed_at": time.time()}
