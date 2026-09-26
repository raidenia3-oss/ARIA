import json
import os
import re
import time
from typing import Optional

from .ai_router import AuraCognitiveRouter
from .memory import (
    init_db,
    create_session,
    add_message,
    get_chat_history,
    clear_history,
)
from .tools import (
    list_files,
    read_file,
    write_file,
    get_system_info,
    execute_shell,
    ALLOWED_COMMANDS,
)
from .memory.knowledge_graph import KnowledgeGraph, bootstrap_ecosystem

init_db()

# ──────────────────────────────────────────
# Knowledge Graph global singleton
# ──────────────────────────────────────────
kg = KnowledgeGraph()
bootstrap_ecosystem(kg)

# ──────────────────────────────────────────
# Sistema de personas
# ──────────────────────────────────────────
PERSONAS_PATH = os.path.join(os.path.dirname(__file__), "personas.json")

with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
    PERSONAS: dict = json.load(f)

CONTEXT_SUMMARY_THRESHOLD = 10
CODING_KEYWORDS = [
    "def ",
    "class ",
    "function",
    "html",
    "test",
    "script",
    "bug",
    "import ",
    "python",
    "javascript",
    "cpp",
    "c++",
    "sql",
    "error",
    "debug",
    "fix",
    "ejecuta",
    "compila",
    "algoritmo",
    "variable",
    "loop",
    "array",
    "lista",
    "código",
    "codigo",
    "archivo",
    "file",
    "lee",
    "leer",
    "escribe",
    "escribir",
    "crea",
    "crear",
    "terminal",
    "comando",
    "consola",
    "log",
]


class AuraBrain:
    def __init__(self, ws_client=None) -> None:
        self.router = AuraCognitiveRouter()
        self.current_persona: str = "AURA Standard"
        self._ws_client = ws_client

    # ──────────────────────────────────────
    # Personas
    # ──────────────────────────────────────
    def set_persona(self, persona_name: str) -> bool:
        if persona_name in PERSONAS:
            self.current_persona = persona_name
            return True
        return False

    def get_persona(self) -> dict:
        return PERSONAS.get(self.current_persona, PERSONAS["AURA Standard"])

    def get_persona_priority(self) -> list[str]:
        return self.get_persona().get("provider_priority", [])

    # ──────────────────────────────────────
    # Detección y elección de proveedor
    # ──────────────────────────────────────
    def detect_intention(self, prompt: str) -> str:
        text = prompt.lower()
        if any(kw in text for kw in CODING_KEYWORDS):
            return "CODING"
        return "GENERAL"

    def choose_provider(self, intention: str) -> str:
        # Si hay persona activa, respetar prioridad
        persona_prio = self.get_persona_priority()
        if persona_prio:
            first = persona_prio[0]
            if first == "ollama" and self.router._is_ollama_available():
                return "ollama"
            if first == "ollama":
                # caer al siguiente de la lista
                for candidate in persona_prio[1:]:
                    if candidate == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
                        return "openrouter"
                    if candidate == "groq" and os.environ.get("GROQ_API_KEY"):
                        return "groq"
                    if candidate == "gemini" and os.environ.get("GEMINI_API_KEY"):
                        return "gemini"
                # último fallback
                if self.router._is_ollama_available():
                    return "ollama"
            if first == "groq" and os.environ.get("GROQ_API_KEY"):
                return "groq"
            if first == "gemini" and os.environ.get("GEMINI_API_KEY"):
                return "gemini"

        # Comportamiento original si no hay persona con prioridad
        if intention == "CODING":
            if self.router._is_ollama_available():
                return "ollama"
            return "openrouter"
        for candidate in ("groq", "gemini"):
            if os.environ.get("GROQ_API_KEY" if candidate == "groq" else "GEMINI_API_KEY"):
                return candidate
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        return "ollama" if self.router._is_ollama_available() else "openrouter"

    # ──────────────────────────────────────
    # Resumen de historial
    # ──────────────────────────────────────
    def summarize_history(self, messages: list[dict]) -> str:
        try:
            if os.environ.get("GROQ_API_KEY"):
                cfg = {
                    "name": "groq",
                    "api_url": "https://api.groq.com/openai/v1/chat/completions",
                    "model": "llama3-8b-8192",
                    "api_key_env": "GROQ_API_KEY",
                    "free_tier": True,
                    "priority": 2,
                }
                api_key = os.environ["GROQ_API_KEY"]
                text_parts = [m["content"] for m in messages]
                joined = "\n".join(text_parts)
                prompt = (
                    "Resume ejecutivamente la siguiente conversación en 3-5 bullets, "
                    "conservando decisiones, intenciones y nombres relevantes:\n\n" + joined
                )
                payload = {
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                import requests

                r = requests.post(cfg["api_url"], headers=headers, json=payload, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content and str(content).strip():
                        return str(content).strip()
        except Exception:
            pass
        bullets = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")[:120]
            bullets.append(f"- {role}: {content}")
        return "\n".join(bullets)

    # ──────────────────────────────────────
    # Tool Use
    # ──────────────────────────────────────
    def _build_tool_prompt(self, user_prompt: str, history: list[dict]) -> str:
        persona = self.get_persona()
        persona_text = persona.get("system_prompt", "")

        tool_desc = (
            f"Perfil activo: {self.current_persona}\n"
            "Herramientas disponibles:\n"
            "- read_file(filename): lee un archivo de C:\\Users\\<nombre> (ej: read_file('test.txt')).\n"
            "- write_file(filename, content): crea/sobrescribe un archivo en C:\\Users\\<nombre>.\n"
            "- list_files(path): lista archivos en una ruta.\n"
            "- get_system_info(): retorna info de CPU, RAM y disco (formato JSON).\n"
            "- execute_shell(command): ejecuta comandos permitidos: "
            + ", ".join(sorted(ALLOWED_COMMANDS))
            + ".\n\n"
            "Cuando necesites usar una herramienta, responde SOLO con un bloque JSON:\n"
            '{"tool": "nombre_herramienta", "args": {"param1": "valor1", ...}}\n\n'
            "Si no necesitas herramientas, responde normal."
        )
        context = "\n".join(m.get("content", "") for m in history[-5:])
        return f"{persona_text}\n\n{tool_desc}\n\nHistorial reciente:\n{context}\n\nUsuario: {user_prompt}\nAURA:"

    def _parse_tool_call(self, text: str):
        text = text.strip()
        if not text.startswith("{"):
            return None, text
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "tool" in data and isinstance(data.get("args"), dict):
                return data, None
        except Exception:
            pass
        return None, text

    def _execute_tool(self, tool_name: str, args: dict) -> dict:
        fn_map = {
            "list_files": lambda a: list_files(a.get("path", r"C:\Users\User")),
            "read_file": lambda a: read_file(a.get("filename", "")),
            "write_file": lambda a: write_file(a.get("filename", ""), a.get("content", "")),
            "get_system_info": lambda a: get_system_info(),
            "execute_shell": lambda a: execute_shell(a.get("command", "")),
        }
        fn = fn_map.get(tool_name)
        if not fn:
            return {"error": f"Herramienta desconocida: {tool_name}"}
        try:
            result = fn(args)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ──────────────────────────────────────
    # Procesamiento principal
    # ──────────────────────────────────────
    def process_input(
        self,
        session_id: int,
        user_prompt: str,
        force_provider: Optional[str] = None,
        tool_authorized: Optional[dict] = None,
    ) -> dict:
        started_at = time.time()

        add_message(session_id, "user", user_prompt)
        history = get_chat_history(session_id, limit=20)

        context_messages = history
        if len(history) > CONTEXT_SUMMARY_THRESHOLD:
            to_summarize = history[: len(history) - CONTEXT_SUMMARY_THRESHOLD + 1]
            summary = self.summarize_history(to_summarize)
            remaining = history[len(to_summarize) :]
            context_messages = [{"role": "system", "content": summary}] + remaining

        intention = self.detect_intention(user_prompt)
        provider = force_provider or self.choose_provider(intention)

        # — Indexar mensaje en Knowledge Graph —
        kg.index_chat_message(user_prompt)

        full_prompt = user_prompt
        if context_messages and context_messages[0].get("role") == "system":
            full_prompt = context_messages[0]["content"] + "\n\nUsuario: " + user_prompt

        # — Inyectar contexto del grafo antes de llamar al router —
        graph_ctx = kg.query_graph_context("Usuario", max_depth=2)
        ctx_relations = graph_ctx.get("relations", [])
        if ctx_relations:
            ctx_text = "Contexto relacional:\n"
            for rel in ctx_relations:
                ctx_text += f"- {rel.get('src')} →({rel.get('rel')})→ {rel.get('dst')}\n"
            full_prompt = ctx_text + "\n" + full_prompt
        # FASE 28 - Enviar grafo al HUD de JARVIS en tiempo real
        self._send_graph_context_to_hud(ctx_relations)

        tool_prompt = self._build_tool_prompt(user_prompt, context_messages)
        tool_result = self.router.route(tool_prompt)
        tool_text = tool_result.get("response") or ""
        tool_data, normal_text = self._parse_tool_call(tool_text)

        tool_used = None
        tool_output = None
        provider_used = provider

        if tool_data:
            tool_used = tool_data.get("tool")
            tool_args = tool_data.get("args", {})

            if tool_used == "execute_shell":
                if not tool_authorized or not tool_authorized.get("granted"):
                    authorized_cmd = tool_args.get("command", "")
                    risky = any(
                        (authorized_cmd or "").lower().startswith(x)
                        for x in {"del", "rm ", "rmdir", "rd ", "format"}
                    )
                    return {
                        "session_id": session_id,
                        "intention": intention,
                        "provider_used": provider_used,
                        "response": (
                            "⚠️ Solicitud de ejecución en terminal pendiente de autorización.\n\n"
                            f"Comando: `{authorized_cmd}`\n\n"
                            "Confirma en la interfaz para ejecutar."
                        ),
                        "tool_pending": tool_data,
                        "tool_risky": risky,
                    }
                authorized_cmd = tool_args.get("command", "")
                base_cmd = authorized_cmd.split()[0] if authorized_cmd else ""
                if base_cmd.lower() not in ALLOWED_COMMANDS:
                    tool_output = {
                        "ok": False,
                        "error": (
                            f"Comando '{authorized_cmd}' no está en la lista de comandos permitidos: "
                            + ", ".join(sorted(ALLOWED_COMMANDS))
                        ),
                    }
                else:
                    tool_output = self._execute_tool(tool_used, tool_args)
            else:
                tool_output = self._execute_tool(tool_used, tool_args)

            tool_feedback = (
                f"Se ejecutó la herramienta `{tool_used}` con éxito.\n"
                f"Resultado:\n```\n{json.dumps(tool_output, ensure_ascii=False, indent=2)}\n```"
            )
            final_prompt = (
                tool_feedback
                + "\n\nCon base en ese resultado, responde al usuario de forma concisa y útil a su mensaje original:\n"
                + user_prompt
            )
            result = self.router.route(final_prompt)
            response_text = result.get("response") or normal_text or "Herramienta ejecutada."
            provider_used = result.get("provider") or provider_used
        else:
            result = self.router.route(full_prompt)
            response_text = (
                result.get("response")
                or normal_text
                or "Lo siento, no pude generar una respuesta en este momento."
            )
            provider_used = result.get("provider") or provider

        if not response_text:
            response_text = "Lo siento, no pude generar una respuesta en este momento."

        add_message(
            session_id,
            "assistant",
            response_text,
            provider_used=provider_used,
            tool_used=tool_used,
            tool_output=(
                json.dumps(tool_output, ensure_ascii=False) if tool_output is not None else None
            ),
        )

        # Log de rendimiento
        elapsed = time.time() - started_at
        self._log_performance(session_id, elapsed, provider_used, tool_used)

        return {
            "session_id": session_id,
            "intention": intention,
            "provider_used": provider_used,
            "response": response_text,
            "tool_used": tool_used,
            "tool_output": tool_output,
        }

    # ──────────────────────────────────────
    # Logs
    # ──────────────────────────────────────
    def _log_performance(
        self, session_id: int, elapsed: float, provider: str, tool: Optional[str]
    ) -> None:
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, "performance.log")
        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "session_id": session_id,
            "elapsed_sec": round(elapsed, 3),
            "provider": provider,
            "tool": tool,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _send_graph_context_to_hud(self, relations: list) -> None:
        """FASE 28: Envía el JSON de relaciones al HUD de JARVIS por WebSocket."""
        ws_client = getattr(self, "_ws_client", None)
        if ws_client is None:
            return
        try:
            payload = {
                "event": "graph_context_update",
                "payload": {"topic": "Usuario", "relations": relations, "status": "ok"},
            }
            message = json.dumps(payload, ensure_ascii=False)
            if hasattr(ws_client, "send_text"):
                ws_client.send_text(message)
            elif hasattr(ws_client, "send"):
                import asyncio

                asyncio.run(ws_client.send(message))
        except Exception as exc:
            print(f"[Brain->HUD] No se pudo enviar el grafo: {exc}")


if __name__ == "__main__":
    brain = AuraBrain()
    session_id = create_session(title="Prueba Brain con Tools")
    print(f"Sesión creada: {session_id}")
    prompts = [
        "Crea un archivo llamado hola_aura.txt con un saludo dentro.",
        "Lee el archivo hola_aura.txt.",
        "¿Cuál es el uso de CPU y RAM?",
    ]
    for prompt in prompts:
        print("\n" + "=" * 70)
        print(f"Usuario: {prompt}")
        result = brain.process_input(session_id, prompt, tool_authorized={"granted": True})
        print(f"Intención: {result['intention']}")
        print(f"Proveedor: {result['provider_used']}")
        print(f"Herramienta: {result.get('tool_used')}")
        print(f"AURA: {result['response']}")
