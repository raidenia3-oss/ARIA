import json
import asyncio
import os
from typing import Any, Dict, List
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel


class KiloTask(BaseModel):
    task_id: str
    objective: str
    context: Dict[str, Any]
    required_tools: List[str] = []
    timeout: int = 300
    callback_url: str = "http://localhost:8000/api/agents/kilo/callback"


class KiloBridge:
    """Interfaz entre AURA y agentes Kilo/Cline"""

    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_history: List[Dict[str, Any]] = []
        self.prompts_dir = Path("kilo_prompts")
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

    async def delegate_task(self, task: KiloTask) -> Dict:
        """Delegar tarea a Kilo"""

        prompt = self._build_kilo_prompt(task)

        self.active_tasks[task.task_id] = {
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "prompt": prompt,
            "objective": task.objective,
        }

        prompt_file = self.prompts_dir / f"{task.task_id}.md"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        return {
            "task_id": task.task_id,
            "status": "delegated",
            "prompt_file": str(prompt_file),
            "message": "Tarea delegada a Kilo. Espera a que la procese.",
        }

    def _build_kilo_prompt(self, task: KiloTask) -> str:
        """Construir prompt profesional para Kilo"""

        context_str = json.dumps(task.context, indent=2, ensure_ascii=False)
        tools_str = "\n".join(f"- {t}" for t in task.required_tools)

        prompt = f"""
╔════════════════════════════════════════════════════════════════════════╗
║                    AURA TASK DELEGATION TO KILO                       ║
╚════════════════════════════════════════════════════════════════════════╝

TASK ID: {task.task_id}
OBJECTIVE: {task.objective}
TIMEOUT: {task.timeout}s
CALLBACK: {task.callback_url}

CONTEXT:
{context_str}

REQUIRED TOOLS:
{tools_str if tools_str else "- Standard CLI tools"}

INSTRUCTIONS:
1. Analiza el objetivo
2. Ejecuta los pasos necesarios
3. Documenta el resultado
4. Envía callback POST a {task.callback_url}

Callback payload debe ser:
{{
  "task_id": "{task.task_id}",
  "status": "completed|failed",
  "result": {{}},
  "error": "si aplica",
  "duration": segundos
}}

COMIENZA AHORA.
"""
        return prompt

    async def handle_callback(self, task_id: str, result: Dict) -> None:
        """Procesar respuesta de Kilo"""

        if task_id in self.active_tasks:
            self.active_tasks[task_id].update({
                "status": result.get("status", "unknown"),
                "result": result.get("result"),
                "error": result.get("error"),
                "completed_at": datetime.now().isoformat(),
                "duration": result.get("duration"),
            })

            self.task_history.append(self.active_tasks[task_id])
            del self.active_tasks[task_id]

    def get_task_status(self, task_id: str) -> Dict:
        """Ver estado de tarea"""
        return self.active_tasks.get(task_id, {"error": "Task not found"})

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Historial de tareas completadas"""
        return self.task_history[-limit:]


kilo_bridge = KiloBridge()
