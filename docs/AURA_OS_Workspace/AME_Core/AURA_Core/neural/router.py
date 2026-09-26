"""AURA Neural Bridge — Enrutador multi-modelo con cola asíncrona."""

from __future__ import annotations

import asyncio
import time
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import httpx

# Configuración base
BASE = Path(__file__).resolve().parent.parent
STATE_FILE = BASE / "neural" / "queue_state.json"
STATUS_FILE = BASE / "neural" / "neural_status.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Endpoints y modelos
OLLAMA_URL = "http://localhost:11434"
DEFAULT_UNCENSORED_MODEL = "deepseek-coder:1.3b"
DEFAULT_CENSORED_MODEL = "deepseek-coder:1.3b"
DEFAULT_CLOUD_MODEL = "external-cloud"

# Timeouts
TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class TaskState:
    task_id: str
    status: str
    prompt: str
    censorship: bool
    model: Optional[str]
    response: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())


class NeuralBridge:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TaskState] = asyncio.Queue()
        self._states: dict[str, TaskState] = {}
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._loop_task is None:
            self._loop_task = asyncio.ensure_future(self._process_loop())

    async def stop(self) -> None:
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None

    async def ask(self, prompt: str, censorship: bool = False, model: Optional[str] = None) -> str:
        task_id = f"task_{int(time.time()*1000)}"
        target_model = model or (DEFAULT_CENSORED_MODEL if censorship else DEFAULT_UNCENSORED_MODEL)
        state = TaskState(
            task_id=task_id,
            status="PENDING",
            prompt=prompt,
            censorship=censorship,
            model=target_model,
        )
        self._states[task_id] = state
        await self._queue.put(state)
        return task_id

    async def get_status(self, task_id: str) -> Optional[TaskState]:
        return self._states.get(task_id)

    async def _process_loop(self) -> None:
        while True:
            state = await self._queue.get()
            try:
                state = self._update_state(state, status="PROCESSING")
                response = await self._call_model(state.prompt, state.model)
                state = self._update_state(state, status="SUCCESS", response=response)
            except Exception as e:
                state = self._update_state(state, status="FAILED", error=str(e))
            finally:
                self._queue.task_done()

    def _update_state(self, state: TaskState, **kwargs) -> TaskState:
        data = asdict(state)
        data.update(kwargs)
        data["updated_at"] = time.time()
        new_state = TaskState(**data)
        self._states[new_state.task_id] = new_state
        self._persist()
        return new_state

    async def _call_model(self, prompt: str, model: str) -> str:
        if model == DEFAULT_CLOUD_MODEL:
            raise RuntimeError("Cloud model not configured")
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                response_text = data.get("response", "")
                if not response_text or not response_text.strip():
                    raise ValueError("Empty response from model provider")
                return response_text
        except Exception as e:
            self._update_hud_status("FALLBACK", f"API error: {e}")
            raise RuntimeError(f"Model call failed: {e}")

    def _persist(self) -> None:
        try:
            serializable = {k: asdict(v) for k, v in self._states.items()}
            STATE_FILE.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _update_hud_status(self, phase: str, detail: str = "") -> None:
        try:
            payload = {
                "phase": phase,
                "detail": detail,
                "updated_at": time.time(),
            }
            STATUS_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _validate_code(self, file_path: Path) -> tuple[bool, str]:
        if file_path.suffix.lower() == ".py":
            try:
                subprocess.run(
                    [sys.executable, "-m", "py_compile", str(file_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return True, ""
            except subprocess.CalledProcessError as e:
                return False, e.stderr or str(e)
        return True, "skip"

    async def execute_autonomous_task(self, task_description: str, max_attempts: int = 3) -> str:
        self._update_hud_status("PLANIFICANDO", task_description)
        plan_prompt = (
            "Desglosa la siguiente tarea en una lista de pasos concretos en formato JSON "
            '{"steps":["1. ...","2. ..."]}.\nTarea: ' + task_description
        )
        plan_task_id = await self.ask(plan_prompt)
        plan_state = await self.get_status(plan_task_id)
        plan_text = ""
        if plan_state and plan_state.status == "SUCCESS":
            plan_text = plan_state.response or ""

        self._update_hud_status("ESCRIBIENDO", "Generando archivos")
        gen_prompt = (
            "Usando este plan:\n"
            + plan_text
            + "\n\n"
            + "Escribe el código modular necesario para la tarea. Responde solo con rutas "
            "y bloques de código."
        )
        gen_task_id = await self.ask(gen_prompt)
        gen_state = await self.get_status(gen_task_id)
        generated = ""
        if gen_state and gen_state.status == "SUCCESS":
            generated = gen_state.response or ""

        self._update_hud_status("VERIFICANDO", "Ejecutando validador")
        output_path = BASE / "neural" / "generated_module.py"
        try:
            output_path.write_text(generated, encoding="utf-8")
        except Exception as e:
            return f"ERROR al escribir archivo: {e}"

        for attempt in range(max_attempts):
            ok, error_msg = self._validate_code(output_path)
            if ok:
                self._update_hud_status("FINALIZADO", "Código válido")
                return f"Código generado en {output_path}"
            self._update_hud_status("AUTODEPURANDO", f"Intento {attempt+1}/{max_attempts}")
            fix_prompt = (
                "Corrige el siguiente código Python para que sea válido. Error:\n"
                + error_msg
                + "\nCódigo:\n"
                + generated
            )
            fix_task_id = await self.ask(fix_prompt)
            fix_state = await self.get_status(fix_task_id)
            if fix_state and fix_state.status == "SUCCESS":
                generated = fix_state.response or generated
                try:
                    output_path.write_text(generated, encoding="utf-8")
                except Exception as e:
                    return f"ERROR al sobrescribir archivo: {e}"
            else:
                continue

        self._update_hud_status("FALLIDO", "Límite de intentos")
        return f"No se pudo validar el código tras {max_attempts} intentos."


neural_bridge = NeuralBridge()
