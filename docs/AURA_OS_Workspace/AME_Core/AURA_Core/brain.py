import os
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
from .tools import run_agent_debate
from .guardrails import (
    init_db as guardrails_init_db,
    check_and_sanitize as guardrails_check,
    filter_credentials,
)

# Inicializar BD al importar
init_db()
guardrails_init_db()

# Umbrales
CONTEXT_SUMMARY_THRESHOLD = 10  # mensajes
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
    "bug",
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
]
DEBATE_KEYWORDS = [
    "analiza los pros y contras",
    "pros y contras",
    "lluvia de ideas",
    "debate",
    "analisis profundo",
    "análisis profundo",
    "agente debate",
    "debate de agentes",
    "analiza el impacto",
    "analiza ventajas y desventajas",
    "ventajas y desventajas",
]


class AuraBrain:
    def __init__(self) -> None:
        self.router = AuraCognitiveRouter()

    def detect_intention(self, prompt: str) -> str:
        text = prompt.lower()
        if any(kw in text for kw in CODING_KEYWORDS):
            return "CODING"
        if any(kw in text for kw in DEBATE_KEYWORDS):
            return "DEBATE"
        return "GENERAL"

    def choose_provider(self, intention: str) -> str:
        if intention == "CODING":
            # Prioriza LM Studio local; si no, OpenRouter
            if self.router._is_ollama_available():
                return "ollama"
            return "openrouter"
        # GENERAL: requiere modelo rápido y económico
        # Orden: groq -> gemini
        for candidate in ("groq", "gemini"):
            if os.environ.get("GROQ_API_KEY" if candidate == "groq" else "GEMINI_API_KEY"):
                return candidate
        # Fallback a openrouter si está configurado
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        # Último recurso
        return "ollama" if self.router._is_ollama_available() else "openrouter"

    def summarize_history(self, messages: list[dict]) -> str:
        # Usa Groq/OpenRouter para resumir; fallback a JOIN simple
        try:
            # Si Groq disponible, usarlo para resumen
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
                r = requests.post(cfg["api_url"], headers=headers, json=payload, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content and str(content).strip():
                        return str(content).strip()
        except Exception:
            pass

        # Fallback básico si no hay resumen IA
        bullets = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")[:120]
            bullets.append(f"- {role}: {content}")
        return "\n".join(bullets)

    def process_input(self, session_id: int, user_prompt: str) -> dict:
        # 0) Guardrails: sanitizar + detectar prompt injection
        guard = guardrails_check(user_prompt)
        if not guard["safe"]:
            add_message(
                session_id,
                "assistant",
                guard["message"],
                provider_used="guardrails",
            )
            return {
                "session_id": session_id,
                "intention": "BLOCKED",
                "provider_used": "guardrails",
                "response": guard["message"],
                "blocked": True,
            }

        safe_prompt = guard["sanitized_input"]
        # 1) Guardar mensaje usuario
        add_message(session_id, "user", safe_prompt)

        # 2) Obtener historial
        history = get_chat_history(session_id, limit=20)

        # 3) Control de saturación: si >10 mensajes, resumir antiguos
        context_messages = history
        if len(history) > CONTEXT_SUMMARY_THRESHOLD:
            to_summarize = history[: len(history) - CONTEXT_SUMMARY_THRESHOLD + 1]
            summary = self.summarize_history(to_summarize)
            # Conservar resumen como primer mensaje del sistema
            remaining = history[len(to_summarize) :]
            context_messages = [{"role": "system", "content": summary}] + remaining

        # 4) Seleccionar proveedor según intención
        intention = self.detect_intention(user_prompt)

        # 4.1) Intencion especial: DEBATE -> ejecutar tool multi-agente
        if intention == "DEBATE":
            debate_result = run_agent_debate(user_prompt)
            # Guardar respuesta sintetizada del debate
            final_report = debate_result.get("final_report") or "Sin reporte consolidado."
            add_message(session_id, "assistant", final_report, provider_used="agent-swarm")
            return {
                "session_id": session_id,
                "intention": intention,
                "provider_used": "agent-swarm",
                "response": final_report,
                "tool_used": "agent_debate",
                "tool_output": debate_result,
            }

        provider = self.choose_provider(intention)

        # 5) Construir contexto para el router
        # AuraCognitiveRouter.route no recibe historial; aquí simulamos
        # Una llamada simple con el prompt actual; para historial,
        # podríamos envolver el prompt con el resumen si existe.
        full_prompt = user_prompt
        if context_messages and context_messages[0].get("role") == "system":
            full_prompt = context_messages[0]["content"] + "\n\nUsuario: " + user_prompt

        # 6) Llamada a router (usa proveedor automático por failover)
        result = self.router.route(full_prompt)

        response_text = result.get("response")
        provider_used = result.get("provider") or provider

        if not response_text:
            response_text = "Lo siento, no pude generar una respuesta en este momento."

        # 7) Filtro de credenciales antes de guardar/mostrar
        response_text = filter_credentials(response_text)

        # 8) Guardar respuesta
        add_message(session_id, "assistant", response_text, provider_used=provider_used)

        return {
            "session_id": session_id,
            "intention": intention,
            "provider_used": provider_used,
            "response": response_text,
        }


# Bloque de prueba
if __name__ == "__main__":
    import requests  # import local para resumen

    brain = AuraBrain()

    # Crear sesión de prueba
    session_id = create_session(title="Prueba Brain")
    print(f"Sesión creada: {session_id}")

    prompts = [
        "Hola, explícame qué es un bucle for en python",
        "Escribe una función que sume dos números",
        "Tengo un bug en este código: def suma(a,b): return a+b",
    ]

    for prompt in prompts:
        print("\n" + "=" * 70)
        print(f"Usuario: {prompt}")
        result = brain.process_input(session_id, prompt)
        print(f"Intención: {result['intention']}")
        print(f"Proveedor: {result['provider_used']}")
        print(f"AURA: {result['response']}")

    print("\n" + "=" * 70)
    print("Historial final (últimos 5 mensajes):")
    for msg in get_chat_history(session_id, limit=5):
        print(f"- [{msg['role']}] {msg['content'][:80]}... (provider: {msg.get('provider_used')})")
