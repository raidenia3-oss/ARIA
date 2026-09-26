"""ARIA Logic Engine — standalone process (no HTTP).
Reads JSON requests from stdin, writes JSON responses to stdout.
Replaces FastAPI backend for IPC-based desktop architecture."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from threading import Thread, Event

from pathlib import Path
from dotenv import load_dotenv
ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
load_dotenv(str(ARIA_APP / ".env"))
LOG_DIR = ARIA_APP / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("ARIA")
logger.setLevel(logging.INFO)
try:
    _fh = logging.FileHandler(LOG_DIR / "aria.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_fh)
except Exception: pass
try:
    _sh = logging.StreamHandler()
    _sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(_sh)
except Exception: pass

for p in [str(ARIA_APP)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("ARIA_SYSTEM_PROMPT",
    "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español.")


class LogicEngine:
    def __init__(self):
        self._running = Event()
        self._running.set()
        self.start_time = time.time()
        self._init_modules()
        logger.info("LogicEngine initialized")

    def _init_modules(self):
        self.skill_registry = None
        self.react_loop = None
        self.ai_manager = None
        self.tool_registry = None
        self.llm_fallback = None
        self.personality = None
        self._load_ai()
        self._load_skills()
        self._load_tools()
        self._init_fallback()

    def _load_ai(self):
        try:
            from ai_providers import AIProviderManager
            self.ai_manager = AIProviderManager()
            logger.info(f"AI: {self.ai_manager.get_available_providers()}")
        except Exception as e:
            logger.warning(f"AI fallback: {e}")
            class _Fallback:
                def __init__(self):
                    self.providers = {"local": {"available": True, "priority": 99}}
                    self._usage = {"requests": 0, "tokens": 0, "providers_used": {}}
                def chat(self, message, history=None, system_prompt="", provider=None):
                    return {"message": "ARIA funcionando en modo local.", "provider": "local", "latency": 0.0}
                def get_available_providers(self): return ["local"]
                def get_best_provider(self): return "local"
                def get_provider_health(self): return {}
                def ping(self): return False
            self.ai_manager = _Fallback()

    def _load_skills(self):
        try:
            from backend.skills.registry import SkillRegistry
            self.skill_registry = SkillRegistry()
            logger.info(f"Skills loaded: {len(self.skill_registry.list())}")
        except Exception as e:
            logger.error(f"SkillRegistry error: {e}")

    def _load_tools(self):
        try:
            from backend.tool_registry import ToolRegistry
            self.tool_registry = ToolRegistry()
            self._register_tools()
            logger.info("ToolRegistry loaded")
        except Exception as e:
            logger.error(f"ToolRegistry error: {e}")

    def _register_tools(self):
        for mod_name, tool_name, category, desc, danger in [
            ("backend.skills.system.control", "control_pc", "system", "Control PC", "dangerous"),
            ("backend.skills.system.explorer", "explorer", "system", "Explorador archivos", "safe"),
            ("backend.skills.system.code_exec", "code_run", "system", "Ejecución código", "cautious"),
            ("backend.skills.web.automation", "browser", "web", "Navegador", "cautious"),
        ]:
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                fn = getattr(mod, "run", None)
                if fn:
                    params = ["action"] if tool_name == "control_pc" else ["action", "path"] if tool_name == "explorer" else ["code"] if tool_name == "code_run" else ["action"]
                    self.tool_registry.register(tool_name, desc, category, fn, params, danger)
                    logger.info(f"Tool registered: {tool_name}")
            except Exception as e:
                logger.warning(f"Tool skip {tool_name}: {e}")

    def _init_fallback(self):
        """Init smart fallback chain and personality engine."""
        try:
            from backend.execution.llm_smart_fallback import SmartLLMFallback
            self.llm_fallback = SmartLLMFallback(timeout=5.0)
            logger.info("SmartLLMFallback initialized")
        except Exception as e:
            logger.warning(f"Fallback init skipped: {e}")
            self.llm_fallback = None
        try:
            from backend.personality.personality_engine import PersonalityEngine
            self.personality = PersonalityEngine()
            logger.info("PersonalityEngine initialized")
        except Exception as e:
            logger.warning(f"Personality init skipped: {e}")
            self.personality = None

    def _build_react_loop(self):
        if self.react_loop is not None:
            return
        try:
            from backend.agent.core import ReactLoop
            mem_cls = None
            try:
                from backend.memory.short_term import ShortTermMemory
                mem_cls = ShortTermMemory
            except Exception: pass
            mem = None
            if mem_cls:
                for path in ["ARIA_APP/memory/short_term.json", "memory/short_term.json", str(LOG_DIR / "short_term.json")]:
                    try:
                        mem = mem_cls(path=path)
                        break
                    except Exception: continue
            self.react_loop = ReactLoop(
                skill_registry=self.skill_registry, memory=mem, ai_manager=self.ai_manager,
            )
            logger.info("ReactLoop built")
        except Exception as e:
            logger.error(f"ReactLoop error: {e}\n{traceback.format_exc()}")

    def handle_chat(self, message, system_prompt=""):
        self._build_react_loop()
        # Try fallback chain first (faster + more reliable)
        if self.llm_fallback:
            try:
                import asyncio
                ctx = {"prompt": message}
                result = asyncio.run(self.llm_fallback.generate_with_fallback(message, system_prompt))
                response_text = result.get("response", "")
                if response_text and self.personality:
                    response_text = self.personality.enhance(response_text, ctx)
                # Confidence score: higher for cache, lower for generic fallback
                source = result.get("source", "fallback")
                latency = result.get("latency", 0.0)
                if source == "cache":
                    confidence = 0.95
                elif source == "ollama":
                    confidence = 0.85 if latency < 5.0 else 0.70
                elif source == "atria":
                    confidence = 0.75
                else:
                    confidence = 0.60
                return {"status": "ok", "response": response_text,
                        "source": source, "latency": latency,
                        "confidence": round(confidence, 2)}
            except Exception as e:
                logger.warning(f"Fallback chain error: {e}")

        if self.react_loop:
            try:
                result = self.react_loop.run(message, system_prompt=system_prompt)
                response_text = result.get("response", "")
                if response_text and self.personality:
                    response_text = self.personality.enhance(response_text, {"prompt": message})
                latency = result.get("latency", 0.0)
                provider = result.get("provider", "local")
                confidence = 0.80 if provider == "local" else 0.70
                return {"status": "ok", "response": response_text,
                        "provider": provider, "latency": latency,
                        "confidence": round(confidence, 2),
                        "plan": result.get("plan"), "executed_steps": result.get("executed_steps")}
            except Exception as e:
                logger.error(f"Chat error: {e}\n{traceback.format_exc()}")
                return {"status": "error", "response": f"Error: {e}"}
        return {"status": "error", "response": "ReAct loop no disponible"}

    def handle_skill(self, skill_name, params=None):
        if not self.skill_registry:
            return {"status": "error", "error": "SkillRegistry no disponible"}
        return self.skill_registry.run(skill_name, params or {})

    def handle_tool(self, tool_name, params=None):
        if not self.tool_registry:
            return {"status": "error", "error": "ToolRegistry no disponible"}
        raw = json.dumps(params or {})
        result = self.tool_registry.execute(tool_name, raw)
        return {"status": "ok" if result.success else "error",
                "tool": tool_name, "output": result.output,
                "error": result.error, "time_ms": result.execution_time_ms}

    def handle_list_skills(self):
        if not self.skill_registry:
            return {"skills": [], "count": 0}
        return {"skills": self.skill_registry.list(), "count": len(self.skill_registry.list())}

    def handle_status(self):
        return {"status": "ok", "skills": len(self.skill_registry.list()) if self.skill_registry else 0,
                "ai_available": hasattr(self.ai_manager, "get_available_providers"),
                "uptime": round(time.time() - self.start_time, 1)}

    def handle_ping(self):
        return {"status": "ok", "type": "pong"}

    def process_request(self, request):
        req_type = request.get("type", "")
        data = request.get("data", {})
        handlers = {
            "chat": lambda: self.handle_chat(data.get("message", ""), data.get("system_prompt", "")),
            "skill": lambda: self.handle_skill(data.get("skill", ""), data.get("params", {})),
            "tool": lambda: self.handle_tool(data.get("tool", ""), data.get("params", {})),
            "list_skills": self.handle_list_skills,
            "status": self.handle_status,
            "ping": self.handle_ping,
        }
        handler = handlers.get(req_type)
        if handler:
            return handler()
        return {"status": "error", "error": f"tipo desconocido: {req_type}"}

    def run(self):
        print("[LOGIC] ARIA Logic Engine iniciado", flush=True)
        while self._running.is_set():
            try:
                chunk = sys.stdin.readline()
                if not chunk:
                    break
                line = chunk.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    response = self.process_request(request)
                    response["id"] = request.get("id")
                    print(json.dumps(response, ensure_ascii=True), flush=True)
                except json.JSONDecodeError:
                    print(json.dumps({"status": "error", "error": "JSON inválido"}), flush=True)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Run error: {e}\n{traceback.format_exc()}")
                print(json.dumps({"status": "error", "error": str(e)}), flush=True)
        logger.info("Engine stopped")
        print("[LOGIC] Engine detenido", flush=True)


def main():
    engine = LogicEngine()
    engine.run()


if __name__ == "__main__":
    main()
