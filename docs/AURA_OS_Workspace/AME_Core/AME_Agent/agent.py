import asyncio, json, os, sys, subprocess
import websockets, requests
from pathlib import Path
from datetime import datetime

class AMEAgent:
    """
    Agente autonomo con modo pasivo y activo.
    Modo pasivo: monitorea AURA, recibe tareas, responde por voz.
    Modo activo: ejecuta tareas interactivamente.
    Incluye optimizacion de tokens y fallback entre modelos.
    """

    VERSION = "2.0.0"
    CONFIG_PATH = Path("/sdcard/ame_config.json")
    WORKSPACE  = Path("/sdcard/AURA_workspace")
    LOG_PATH   = Path("/sdcard/ame_agent.log")

    def __init__(self):
        self.config   = self._load_config()
        self.ws       = None
        self.llm      = LLMClient(self.config)
        self.tools    = ToolRegistry(self)
        self.memory   = AgentMemory()
        self.running  = False
        self.passive  = self.config.get("passive_mode", True)
        self.opt      = TokenOptimizer(self)

    def _load_config(self) -> dict:
        defaults = {
            "aura_url":     "ws://192.168.1.100:8765",
            "model":        "gemini-flash",
            "node_id":      "AME_AGENT_01",
            "workspace":    "/sdcard/AURA_workspace",
            "auto_approve": False,
            "max_retries":  3,
            "passive_mode": True,       # modo pasivo por defecto
            "passive_interval": 30,     # segundos entre ciclos pasivos
            "max_tokens_per_task": 2000,
            "cache_responses": True,
        }
        if self.CONFIG_PATH.exists():
            try:
                saved = json.loads(self.CONFIG_PATH.read_text())
                defaults.update(saved)
            except Exception:
                pass
        return defaults

    async def connect_aura(self):
        url = self.config["aura_url"]
        try:
            self.ws = await websockets.connect(
                url, ping_interval=20, ping_timeout=10)
            await self._send("AME_AGENT_ONLINE", {
                "version": self.VERSION,
                "capabilities": self.tools.list_capabilities(),
                "node_id": self.config["node_id"],
                "mode": "passive" if self.passive else "active",
            })
            self._log(f"Conectado a AURA: {url}")
            return True
        except Exception as e:
            self._log(f"Sin conexion a AURA: {e}")
            return False

    async def _send(self, event: str, payload: dict):
        if self.ws and self.ws.open:
            await self.ws.send(json.dumps({
                "node": "AME_AGENT", "event": event,
                "payload": payload, "ts": datetime.now().isoformat()
            }))

    # ── MODO PASIVO ──────────────────────────────

    async def run_passive(self):
        """Modo pasivo: escucha tareas de AURA y las ejecuta sin interactuar."""
        self.passive = True
        self.running = True
        await self.connect_aura()
        self._log("Modo PASIVO activo - escuchando tareas de AURA...")

        # Registrar handler para tareas entrantes
        if self.ws:
            asyncio.create_task(self._listen_for_tasks())

        # Loop pasivo: mantener conexion viva, reportar estado
        while self.running:
            try:
                await asyncio.sleep(self.config["passive_interval"])
                if self.ws and self.ws.open:
                    await self._send("HEARTBEAT", {
                        "mode": "passive",
                        "llm_status": self.llm.get_status(),
                        "tasks_today": len(self.memory.history),
                    })
            except Exception as e:
                self._log(f"Error en loop pasivo: {e}")
                await asyncio.sleep(5)

    async def _listen_for_tasks(self):
        """Escuchar tareas entrantes de AURA en modo pasivo."""
        if not self.ws:
            return
        try:
            async for message in self.ws:
                msg = json.loads(message)
                if msg.get("event") == "AGENT_NEW_TASK":
                    task_input = msg.get("payload", {}).get("input", "")
                    if task_input:
                        self._log(f"[PASIVO] Tarea recibida: {task_input}")
                        await self.execute_task(task_input)
                elif msg.get("event") == "AGENT_CONFIG":
                    # Actualizar config en caliente
                    new_config = msg.get("payload", {})
                    self.config.update(new_config)
        except Exception as e:
            self._log(f"Error escuchando tareas: {e}")

    # ── MODO ACTIVO ──────────────────────────────

    async def run(self, task: str = None):
        """Modo activo: interactivo con el usuario."""
        self.running = True
        self.passive = False
        await self.connect_aura()
        if task:
            result = await self.execute_task(task)
            print(result)
        else:
            await self._interactive_loop()

    async def _interactive_loop(self):
        print(f"\n{'='*50}")
        print(f"  AME Agent v{self.VERSION}")
        print(f"  Escribe tu tarea o 'salir' para terminar")
        print(f"{'='*50}\n")
        while self.running:
            try:
                task = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("AME > ").strip())
                if task.lower() in ["salir", "exit", "quit"]:
                    print("AME Agent apagado")
                    break
                elif task.lower() == "status":
                    self._print_status()
                elif task.lower() == "historial":
                    self.memory.print_history()
                elif task.lower() == "modelos":
                    self._print_models()
                elif task:
                    result = await self.execute_task(task)
                    print(f"\n{result}\n")
            except KeyboardInterrupt:
                print("\nTerminando...")
                break

    # ── EJECUCION DE TAREAS ──────────────────────

    async def execute_task(self, task: str) -> str:
        self._log(f"Tarea: {task}")
        await self._send("TASK_STARTED", {"task": task, "passive": self.passive})

        # Optimizar: cachear respuestas similares
        cached = self.opt.check_cache(task)
        if cached:
            self._log("Respuesta cacheada reutilizada")
            return cached

        context = {
            "task": task,
            "workspace": str(self.WORKSPACE),
            "aura_connected": self.ws is not None,
            "tools": self.tools.list_capabilities(),
            "memory": self.memory.get_relevant(task),
            "system_info": {"platform": "Android/Termux", "mode": "passive" if self.passive else "active"},
            "budget_remaining": self.opt.get_budget(),
        }

        steps_taken = []
        retries = 0
        while retries < self.config["max_retries"]:
            plan = await self.llm.plan(context)
            if not plan.get("steps"):
                break
            for step in plan["steps"]:
                tool_name = step.get("tool")
                tool_args = step.get("args", {})
                if not self.passive and not self.config["auto_approve"]:
                    confirm = self._confirm_step(tool_name, tool_args)
                    if not confirm:
                        continue
                result = await self.tools.run(tool_name, tool_args)
                steps_taken.append({"tool": tool_name, "args": tool_args, "result": result})
                context["last_result"] = result
                if result.get("error"):
                    retries += 1
                    break
            else:
                break

        self.memory.save(task, steps_taken)
        self.opt.record_task(task, steps_taken)
        await self._send("TASK_COMPLETE", {
            "task": task, "steps": len(steps_taken),
            "passive": self.passive,
        })
        return self._format_result(task, steps_taken)

    def _confirm_step(self, tool, args):
        print(f"\nEjecutar: {tool}")
        print(f"   Args: {json.dumps(args, indent=2)}")
        resp = input("   Confirmar? (s/n/auto): ").strip().lower()
        if resp == "auto":
            self.config["auto_approve"] = True
            return True
        return resp in ["s", "si", "y", "yes", ""]

    def _format_result(self, task, steps):
        lines = [f"Tarea completada: {task}",
                 f"   Pasos ejecutados: {len(steps)}"]
        for i, s in enumerate(steps, 1):
            status = "OK" if not s["result"].get("error") else "FAIL"
            lines.append(f"   {i}. [{status}] {s['tool']}")
        return "\n".join(lines)

    def _print_status(self):
        print(f"\n{'='*40}")
        print(f"AME Agent v{self.VERSION}")
        print(f"Modo: {'PASIVO' if self.passive else 'ACTIVO'}")
        print(f"AURA: {'Conectado' if self.ws else 'Offline'}")
        print(f"Modelos: {json.dumps(self.llm.get_status(), indent=2)}")
        print(f"Cache: {len(self.opt.cache)} entradas")
        print(f"Tareas: {len(self.memory.history)}")
        print(f"{'='*40}\n")

    def _print_models(self):
        status = self.llm.get_status()
        print(f"\n{'='*40}")
        print(f"Modelo actual: {status['current']}")
        for p in status["providers"]:
            icon = "ON" if p["can_use"] else "OFF"
            limit = f"/{p['daily_limit']}" if p["daily_limit"] else "inf"
            print(f"  [{icon}] {p['name']}: {p['tokens_today']}{limit}")
        print(f"{'='*40}\n")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        try:
            with open(self.LOG_PATH, "a") as f:
                f.write(line + "\n")
        except Exception:
            pass


class TokenOptimizer:
    """Optimiza uso de tokens: cache, budget, metricas."""
    def __init__(self, agent):
        self.agent = agent
        self.cache: dict[str, str] = {}
        self.daily_tasks = 0
        self.daily_tokens = 0

    def check_cache(self, task: str) -> str | None:
        if not self.agent.config.get("cache_responses"):
            return None
        return self.cache.get(task.lower().strip())

    def record_task(self, task: str, steps: list):
        self.daily_tasks += 1
        key = task.lower().strip()
        result_str = f"{len(steps)} pasos ejecutados"
        self.cache[key] = result_str
        # Limitar cache a 50 entradas
        if len(self.cache) > 50:
            oldest = list(self.cache.keys())[0]
            del self.cache[oldest]

    def get_budget(self) -> dict:
        status = self.agent.llm.get_status()
        return {
            "tasks_today": self.daily_tasks,
            "models_available": sum(1 for p in status["providers"] if p["can_use"]),
            "current_model": status["current"],
        }


# Importar al final para evitar circular imports
from llm_client import LLMClient
from tools import ToolRegistry
from memory import AgentMemory


if __name__ == "__main__":
    agent = AMEAgent()
    if "--passive" in sys.argv or "-p" in sys.argv:
        asyncio.run(agent.run_passive())
    else:
        task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
        asyncio.run(agent.run(task))