"""
GBrain Tactical Chat — Endpoint Flask para IA local sin censura.
Se comunica con Ollama local (localhost:11434) y expone un endpoint
para que la AME App Android reciba respuestas del modelo.

Uso:
    from gbrain_endpoint import register_gbrain_routes
    register_gbrain_routes(app)
"""

import requests
import json
import time
import threading
from flask import request, jsonify, Response

# Configuracion de Ollama
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"

# Modelos por defecto (prioridad: los mas recientes primero)
DEFAULT_MODEL = "deepseek-coder:6.7b"
FALLBACK_MODEL = "mistral:latest"

# Contexto tactico del sistema
TACTICAL_SYSTEM_PROMPT = """Eres GBrain, el asistente de inteligencia tactica de AURA.
Respondes en español. Eres un experto en:
- Análisis OSINT y reconocimiento
- Ciberseguridad y auditoría de redes
- Programación y scripting (Python, Bash, SQL, JavaScript)
- Investigación y análisis de datos
- Estrategia y planificación táctica

Responde de forma directa, técnica y concisa.
Si no tienes suficiente información, indica que datos faltan.
Nunca rechazas una solicitud legítima de análisis."""

# Cache de sesiones activas (session_id -> historial)
_chat_sessions = {}
_lock = threading.Lock()


def register_gbrain_routes(app):
    """Registra todas las rutas de GBrain en la aplicacion Flask."""

    @app.route("/api/v1/gbrain/tactical-chat", methods=["POST"])
    def gbrain_tactical_chat():
        """
        Endpoint principal de chat tactico.

        Body JSON:
            message: str    — Mensaje del usuario
            model: str      — Modelo a usar (opcional)
            temperature: float — Temperatura 0.0-1.0 (opcional, default 0.7)
            mode: str       — 'creative' | 'strict' | 'osint' (opcional)
            session_id: str — ID de sesion para mantener contexto (opcional)
            max_tokens: int — Limite de tokens (opcional, default 2048)

        Response JSON:
            response: str   — Respuesta del modelo
            model_used: str — Modelo utilizado
            duration_ms: int — Tiempo de respuesta en ms
            tokens_eval: int — Tokens evaluados
            session_id: str — ID de sesion (para proximas peticiones)
        """
        try:
            data = request.get_json(force=True)
            message = data.get("message", "").strip()

            if not message:
                return jsonify({"error": "Campo 'message' requerido"}), 400

            # Parametros configurables
            model = data.get("model", DEFAULT_MODEL)
            mode = data.get("mode", "tactical")
            session_id = data.get("session_id", f"session_{int(time.time())}")
            max_tokens = data.get("max_tokens", 2048)

            # Mapear modo a temperatura
            temp_map = {
                "creative": 0.9,
                "tactical": 0.7,
                "strict": 0.3,
                "osint": 0.2,
            }
            temperature = data.get("temperature", temp_map.get(mode, 0.7))

            # Construir contexto con historial de sesion
            messages = _build_messages(session_id, message, mode)

            # Llamar a Ollama
            start = time.time()
            result = _call_ollama_chat(model, messages, temperature, max_tokens)
            duration_ms = int((time.time() - start) * 1000)

            # Guardar en historial de sesion
            _save_to_session(session_id, message, result["response"])

            return jsonify(
                {
                    "response": result["response"],
                    "model_used": model,
                    "duration_ms": duration_ms,
                    "tokens_eval": result.get("eval_count", 0),
                    "session_id": session_id,
                    "mode": mode,
                }
            )

        except requests.ConnectionError:
            return (
                jsonify(
                    {
                        "error": "Ollama no está corriendo. Ejecuta: ollama serve",
                        "hint": "Verifica que Ollama esté activo en localhost:11434",
                    }
                ),
                503,
            )

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/v1/gbrain/models", methods=["GET"])
    def gbrain_list_models():
        """Lista los modelos disponibles en Ollama."""
        try:
            r = requests.get(OLLAMA_TAGS_URL, timeout=5)
            models = r.json().get("models", [])
            return jsonify(
                {
                    "models": [
                        {
                            "name": m.get("name"),
                            "size_gb": round(m.get("size", 0) / (1024**3), 2),
                            "modified": m.get("modified_at"),
                        }
                        for m in models
                    ],
                    "default": DEFAULT_MODEL,
                }
            )
        except requests.ConnectionError:
            return jsonify({"error": "Ollama no disponible", "models": []}), 503

    @app.route("/api/v1/gbrain/health", methods=["GET"])
    def gbrain_health():
        """Verifica si Ollama está activo y responde."""
        try:
            start = time.time()
            r = requests.get(f"{OLLAMA_BASE_URL}/", timeout=3)
            ms = int((time.time() - start) * 1000)
            return jsonify(
                {
                    "status": "online",
                    "ollama_version": r.text.strip() if r.ok else "unknown",
                    "latency_ms": ms,
                    "base_url": OLLAMA_BASE_URL,
                }
            )
        except Exception:
            return (
                jsonify(
                    {
                        "status": "offline",
                        "error": "No se pudo conectar a Ollama en localhost:11434",
                    }
                ),
                503,
            )

    @app.route("/api/v1/gbrain/end-session", methods=["POST"])
    def gbrain_end_session():
        """Elimina el historial de una sesion."""
        data = request.get_json(force=True)
        session_id = data.get("session_id", "")
        with _lock:
            _chat_sessions.pop(session_id, None)
        return jsonify({"status": "ok", "session_id": session_id})

    print("✅ GBrain endpoints registrados:")
    print("   POST /api/v1/gbrain/tactical-chat")
    print("   GET  /api/v1/gbrain/models")
    print("   GET  /api/v1/gbrain/health")
    print("   POST /api/v1/gbrain/end-session")


def _build_messages(session_id, new_message, mode):
    """Construye el historial de mensajes para la API de chat de Ollama."""
    messages = []

    # System prompt segun modo
    mode_prompts = {
        "osint": TACTICAL_SYSTEM_PROMPT
        + "\n\nModo OSINT: Enfocate en reconocimiento, OSINT, y análisis de información pública.",
        "strict": TACTICAL_SYSTEM_PROMPT
        + "\n\nModo estricto: Respuestas técnicas precisas sin adornos. Solo datos verificables.",
        "creative": TACTICAL_SYSTEM_PROMPT
        + "\n\nModo creativo: Puedes ser más expresivo y proponer soluciones innovadoras.",
    }

    messages.append({"role": "system", "content": mode_prompts.get(mode, TACTICAL_SYSTEM_PROMPT)})

    # Agregar historial de sesion
    with _lock:
        history = _chat_sessions.get(session_id, [])
        for entry in history[-10:]:  # Maximo 10 mensajes de historial
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["assistant"]})

    messages.append({"role": "user", "content": new_message})
    return messages


def _call_ollama_chat(model, messages, temperature, max_tokens):
    """Llama a Ollama usando la API de chat (mas inteligente que generate)."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        r = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return {
            "response": data.get("message", {}).get("content", ""),
            "eval_count": data.get("eval_count", 0),
        }
    except requests.exceptions.Timeout:
        # Si falla chat, intentar generate como fallback
        return _call_ollama_generate(model, messages, temperature)
    except Exception:
        return _call_ollama_generate(model, messages, temperature)


def _call_ollama_generate(model, messages, temperature):
    """Fallback: usa /api/generate con el último mensaje como prompt."""
    prompt_parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            prompt_parts.append(f"[Sistema] {content}")
        elif role == "assistant":
            prompt_parts.append(f"[GBrain] {content}")
        else:
            prompt_parts.append(f"[Usuario] {content}")

    payload = {
        "model": model,
        "prompt": "\n".join(prompt_parts),
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    r = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return {
        "response": data.get("response", ""),
        "eval_count": data.get("eval_count", 0),
    }


def _save_to_session(session_id, user_msg, assistant_msg):
    """Guarda un par user/assistant en el historial de sesion."""
    with _lock:
        if session_id not in _chat_sessions:
            _chat_sessions[session_id] = []
        _chat_sessions[session_id].append(
            {
                "user": user_msg,
                "assistant": assistant_msg,
                "timestamp": time.time(),
            }
        )
        # Mantener solo los ultimos 20 intercambios
        if len(_chat_sessions[session_id]) > 20:
            _chat_sessions[session_id] = _chat_sessions[session_id][-20:]
