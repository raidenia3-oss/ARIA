"""
AURA Cognitive Router — ai_router.py v4
Enruta peticiones de IA al mejor modelo según el tipo de tarea.
Integra la lógica del router.py legacy (Ollama local) + APIs cloud gratuitas.

Novedades v4:
  - Sistema de Failover robusto entre 5 proveedores
  - Soporte completo para OpenRouter, Groq, Gemini, Mistral, Cerebras
  - Carga automática de .env para API Keys
  - Testing seguro sin exponer claves
  - DeepSeek como modelo por defecto (Spectre)
"""

import os
import json
import sys
import requests
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from dotenv import load_dotenv

# Importar el nuevo router cloud
from AURA_Core.neural.cloud_router import HFCloudRouter

try:
    from gradio_client import Client
except ImportError:  # pragma: no cover - optional dependency
    Client = None

# ──────────────────────────────────────────
# Carga de variables de entorno desde .env
# ──────────────────────────────────────────
_env_loaded = False
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        _env_loaded = True
except Exception:
    _env_loaded = False

if not _env_loaded:
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

# ──────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = "deepseek-r1:8b"

# Modelos por conciencia (del router.py legacy)
CONSCIOUSNESS_MODELS = {
    "C-01": "dolphin-llama3:8b",
    "C-02": "deepseek-r1:8b",
    "C-03": "qwen2.5:7b",
    "C-04": "llama3.2:3b",
    "CORE": DEFAULT_MODEL,
}

# Palabras clave para detectar tipo de tarea (del router.py legacy)
ROUTING_RULES = {
    "code": {
        "model": "qwen2.5-coder:7b",
        "keywords": [
            "código",
            "codigo",
            "code",
            "programa",
            "script",
            "función",
            "funcion",
            "class",
            "def ",
            "import ",
            "python",
            "javascript",
            "cpp",
            "c++",
            "html",
            "css",
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
        ],
    },
    "vision": {
        "model": "llama3.2-vision:11b",
        "keywords": [
            "imagen",
            "image",
            "foto",
            "picture",
            "analiza esta",
            "describe esta",
            "qué ves",
            "que ves",
            "mira esto",
            "screenshot",
            "captura",
        ],
    },
    "fast_vision": {
        "model": "moondream",
        "keywords": ["descripción rápida", "describe rápido", "imagen rápida", "foto rápida"],
    },
    "reasoning": {
        "model": "deepseek-r1:8b",
        "keywords": [
            "razona",
            "analiza",
            "explica paso a paso",
            "por qué",
            "por que",
            "cómo funciona",
            "como funciona",
            "deduce",
            "calcula",
            "matemática",
            "matematica",
            "lógica",
            "logica",
            "filosofía",
            "filosofia",
            "estrategia",
            "planifica",
            "decide",
            "compara",
            "evalúa",
            "evalua",
        ],
    },
    "advanced": {
        "model": "gemma3:12b",
        "keywords": ["avanzado", "complejo", "detallado", "profundo", "sofisticado"],
    },
    "multilingual": {
        "model": "qwen2.5:7b",
        "keywords": [
            "traduce",
            "translate",
            "japonés",
            "japones",
            "chino",
            "korean",
            "french",
            "deutsch",
            "arabic",
            "hindi",
            "en inglés",
            "en ingles",
            "en español",
            "en espanol",
        ],
    },
    "fast": {
        "model": "llama3.2:3b",
        "keywords": [
            "rápido",
            "rapido",
            "breve",
            "corto",
            "simple",
            "sencillo",
            "en una palabra",
            "sí o no",
            "si o no",
        ],
    },
}

# ──────────────────────────────────────────
# Proveedores cloud con orden de failover (API keys desde .env)
# ORDEN DE FAILOVER: OpenRouter → Groq → Gemini → Mistral → Cerebras → HF Cloud
# ──────────────────────────────────────────
CLOUD_PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "api_url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openai/gpt-3.5-turbo-instruct",
        "api_key_env": "OPENROUTER_API_KEY",
        "free_tier": True,
        "priority": 1,
    },
    "groq": {
        "name": "Groq",
        "api_url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "mixtral-8x7b-32768",
        "api_key_env": "GROQ_API_KEY",
        "free_tier": True,
        "priority": 2,
    },
    "gemini": {
        "name": "Google Gemini",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent",
        "model": "gemini-pro",
        "api_key_env": "GEMINI_API_KEY",
        "free_tier": True,
        "priority": 3,
        "uses_google_format": True,
    },
    "mistral": {
        "name": "Mistral AI",
        "api_url": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-7b-instruct-v0.2",
        "api_key_env": "MISTRAL_API_KEY",
        "free_tier": True,
        "priority": 4,
    },
    "cerebras": {
        "name": "Cerebras",
        "api_url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "cerebras-7b",
        "api_key_env": "CEREBRAS_API_KEY",
        "free_tier": True,
        "priority": 5,
    },
    "hf_cloud": {
        "name": "HuggingFace Cloud",
        "api_url": "hf_cloud",  # Marcador para el router interno
        "model": "qwen/hermes",  # Se usará el modelo específico del HFCloudRouter
        "api_key_env": "HF_TOKEN",
        "free_tier": True,
        "priority": 6,
    },
}

# Orden de failover (por prioridad)
FAILOVER_ORDER = sorted(
    [(name, cfg) for name, cfg in CLOUD_PROVIDERS.items()], key=lambda x: x[1].get("priority", 999)
)

FAILOVER_ORDER.extend(
    [
        (
            "hf_space",
            {
                "name": "HuggingFace Space",
                "priority": 10,
                "api_url": os.environ.get("HF_SPACE_URL", "").strip(),
                "model": os.environ.get("HF_SPACE_MODEL", "hf_space"),
                "api_key_env": "HF_TOKEN",
                "free_tier": True,
            },
        ),
        (
            "colab",
            {
                "name": "Colab/Ngrok",
                "priority": 11,
                "api_url": "colab",
                "model": "colab",
                "api_key_env": "COLAB_API_KEY",
                "free_tier": True,
            },
        ),
    ]
)


def _colab_config_path() -> Path:
    return Path(__file__).parent.parent / "ame_nube.json"


def _load_colab_config() -> Optional[Dict[str, Any]]:
    path = _colab_config_path()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class AuraCognitiveRouter:
    """
    Cerebro del ecosistema AURA.
    Enruta prompts al modelo adecuado: Ollama local (prioridad) o cloud APIs.

    v3: Soporte para intercepción VOID + command routing.
    """

    def __init__(self):
        self._ollama_available = None  # cache de disponibilidad
        self._hf_cloud_router = HFCloudRouter()  # Instanciar el router HF Cloud

    # ──────────────────────────────────────────
    # Comandos especiales (VOID, etc.)
    # ──────────────────────────────────────────

    VOID_KEYWORDS = [
        "guarda",
        "void:",
        "recuerda",
        "apunta esto",
        "memoriza",
        "registra",
        "nota:",
        "importante:",
        "guardar:",
    ]

    def _detect_void_command(self, prompt: str) -> Optional[Dict]:
        """
        Detecta si el usuario quiere guardar algo en VOID.
        Retorna dict con {action, content, tags} o None.
        """
        prompt_lower = prompt.lower().strip()

        # Comando explícito: "void: contenido" o "guarda: contenido"
        for prefix in ["void:", "guarda:", "nota:", "guardar:"]:
            if prompt_lower.startswith(prefix):
                content = prompt[len(prefix) :].strip()
                if content:
                    return {
                        "action": "save_to_void",
                        "content": content,
                        "tags": ["dashboard", "chat", "void"],
                    }

        # Detección por keyword
        if any(kw in prompt_lower for kw in self.VOID_KEYWORDS):
            return {
                "action": "save_to_void",
                "content": prompt,
                "tags": ["dashboard", "chat", "auto_detect"],
            }

        return None

    def _execute_void_save(self, content: str, tags: List[str]) -> Dict:
        """Guardar en VOID y retornar resultado."""
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from void import save_to_void

            result = save_to_void(content=content, tags=tags)
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ──────────────────────────────────────────
    # API Pública
    # ──────────────────────────────────────────

    def route(self, prompt: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Recibe un prompt y lo envía al mejor modelo disponible.

        Prioridad:
          1. Ollama local (si disponible)
          2. Cloud APIs en orden de failover:
             - OpenRouter → Groq → Gemini → Mistral → Cerebras

        Retorna: {
            "provider": "ollama|openrouter|groq|gemini|mistral|cerebras|None",
            "response": "...",
            "model": "...",
            "task_type": "...",
            "fallback_info": {...}  # Si se usó failover
        }
        """
        has_image = (context or {}).get("has_image", False)
        task_type = self._detect_task_type(prompt)
        fallback_info = {"attempted": [], "failed": []}

        # 1. Intentar Ollama local primero (mejor rendimiento)
        if self._is_ollama_available():
            model = self._get_best_model(prompt, has_image)
            response, model_used = self._call_ollama(prompt, model)
            if response:
                return {
                    "provider": "ollama",
                    "response": response,
                    "model": model_used,
                    "task_type": task_type,
                }

        # 2. Failover a Cloud APIs en orden de prioridad
        for provider_name, cfg in FAILOVER_ORDER:
            api_key = os.environ.get(cfg["api_key_env"])
            if provider_name in {"hf_space", "colab"}:
                if provider_name == "hf_space" and not cfg.get("api_url"):
                    fallback_info["failed"].append(
                        {"provider": provider_name, "reason": "not_configured"}
                    )
                    continue
                if provider_name == "colab" and not _load_colab_config():
                    fallback_info["failed"].append(
                        {"provider": provider_name, "reason": "not_configured"}
                    )
                    continue
            elif not api_key:
                fallback_info["failed"].append({"provider": provider_name, "reason": "no_api_key"})
                continue

            fallback_info["attempted"].append(provider_name)
            response = self._call_cloud(provider_name, cfg, prompt)

            if response:
                return {
                    "provider": provider_name,
                    "response": response,
                    "model": cfg.get("model"),
                    "task_type": task_type,
                    "fallback_info": fallback_info if len(fallback_info["attempted"]) > 1 else None,
                }
            else:
                fallback_info["failed"].append(
                    {"provider": provider_name, "reason": "request_failed"}
                )

        # 3. Si todos fallan
        return {
            "provider": None,
            "response": None,
            "model": None,
            "error": "No providers available",
            "task_type": task_type,
            "fallback_info": fallback_info,
        }

    def route_with_void(self, prompt: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Versión inteligente de route():
        - Si detecta comando VOID → guarda y responde confirmación
        - Si no → ruteo normal con IA
        """
        void_cmd = self._detect_void_command(prompt)

        if void_cmd:
            result = self._execute_void_save(content=void_cmd["content"], tags=void_cmd["tags"])
            if result.get("status") == "ok":
                return {
                    "provider": "void",
                    "model": "void_memory",
                    "response": "🧠 Entendido. Registrado en el **VOID** de forma segura.",
                    "task_type": "void_save",
                    "void_result": result,
                }
            else:
                return {
                    "provider": "void",
                    "model": "void_memory",
                    "response": f"⚠️ Error al guardar en VOID: {result.get('error', 'desconocido')}",
                    "task_type": "void_error",
                    "void_result": result,
                }

        # No es comando VOID → ruteo normal
        return self.route(prompt, context)

    def list_available_providers(self) -> List[Dict]:
        """Lista proveedores disponibles (Ollama + cloud con API key)."""
        providers = []

        if self._is_ollama_available():
            providers.append(
                {
                    "name": "ollama",
                    "type": "local",
                    "models": list(set(r["model"] for r in ROUTING_RULES.values())),
                }
            )

        for name, cfg in CLOUD_PROVIDERS.items():
            key = os.environ.get(cfg["api_key_env"])
            if key:
                providers.append(
                    {
                        "name": name,
                        "model": cfg["model"],
                        "free_tier": cfg["free_tier"],
                    }
                )

        return providers

    # ──────────────────────────────────────────
    # Detección de tarea (desde router.py legacy)
    # ──────────────────────────────────────────

    def _detect_task_type(self, message: str) -> str:
        """Analiza el mensaje y devuelve el tipo de tarea."""
        message_lower = message.lower()

        if "[imagen" in message_lower or "[image" in message_lower or "[foto" in message_lower:
            return "vision"

        scores = {task: 0 for task in ROUTING_RULES}
        for task, config in ROUTING_RULES.items():
            for keyword in config["keywords"]:
                if keyword in message_lower:
                    scores[task] += 1

        max_score = max(scores.values())
        if max_score == 0:
            return "default"

        return max(scores, key=scores.get)

    def _get_best_model(self, message: str, has_image: bool = False) -> str:
        """Selecciona el mejor modelo Ollama según el mensaje."""
        if has_image:
            return ROUTING_RULES["vision"]["model"]

        task_type = self._detect_task_type(message)
        if task_type == "default":
            return DEFAULT_MODEL
        return ROUTING_RULES[task_type]["model"]

    # ──────────────────────────────────────────
    # Llamadas a proveedores
    # ──────────────────────────────────────────

    def _is_ollama_available(self) -> bool:
        """Verifica si Ollama está corriendo localmente."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            res = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
            self._ollama_available = res.status_code == 200
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _call_ollama(self, prompt: str, model: str) -> Tuple[Optional[str], Optional[str]]:
        """Envía prompt a Ollama local."""
        try:
            res = requests.post(
                f"{OLLAMA_BASE}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                headers={"Content-Type": "application/json"},
                timeout=120.0,
            )
            if res.status_code == 200:
                data = res.json()
                content = data.get("message", {}).get("content", "")
                if content:
                    return content, model
        except Exception:
            pass
        return None, model

    def _call_cloud(self, provider_name: str, cfg: Dict, prompt: str) -> Optional[str]:
        """
        Envía prompt a una API cloud con manejo robusto de errores.
        Soporta múltiples formatos de API (OpenAI-compatible + Google Gemini).
        Delega a proveedores URL-based (hf_space, colab) cuando aplica.

        NO registra las API keys en logs por seguridad.
        """
        if provider_name == "hf_cloud":
            task_type = self._detect_task_type(prompt)
            # El método _call_hf_cloud es async, lo ejecutamos con asyncio.run
            return asyncio.run(self._call_hf_cloud(task_type, prompt))
        if provider_name == "hf_space":
            return self._call_hf_space(cfg, prompt)
        if provider_name == "colab":
            return self._call_colab(prompt)

        api_key = os.environ.get(cfg["api_key_env"])
        if not api_key:
            return None

        try:
            # Formato especial para Google Gemini
            if cfg.get("uses_google_format"):
                url = f"{cfg['api_url']}?key={api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                headers = {"Content-Type": "application/json"}

                res = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except ValueError:
                        return None
                    try:
                        content = (
                            data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        )
                        if not content or not str(content).strip():
                            raise ValueError("Empty response from cloud provider (Gemini)")
                        return content
                    except (IndexError, KeyError, TypeError, ValueError):
                        return None
            else:
                # Formato OpenAI-compatible (OpenRouter, Groq, Mistral, Cerebras)
                res = requests.post(
                    cfg["api_url"],
                    json={
                        "model": cfg["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "max_tokens": 128,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except ValueError:
                        return None
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if not content or not str(content).strip():
                        raise ValueError("Empty response from cloud provider")
                    return content
                elif res.status_code == 429:
                    # Rate limit - registrar sin exponer la clave
                    return None
                elif res.status_code == 401:
                    # Unauthorized - puede ser API key inválida
                    return None

        except requests.Timeout:
            # Timeout - el proveedor no respondió a tiempo
            pass
        except requests.ConnectionError:
            # Error de conexión
            pass
        except Exception:
            # Otros errores (JSON parsing, etc.)
            pass

        return None

    async def _call_hf_cloud(self, task_type: str, prompt: str) -> Optional[str]:
        """
        Envía un prompt al HFCloudRouter.
        Usa el modelo 'coder' si la tarea es de código, 'agent' para otros.
        """
        try:
            if "code" in task_type:
                return await self._hf_cloud_router.generate_code(prompt)
            else:
                return await self._hf_cloud_router.generate_chat(prompt)
        except Exception:
            return None

    def _call_hf_space(self, cfg: Dict, prompt: str) -> Optional[str]:
        """
        Envía un prompt a un HuggingFace Space vía Gradio Client.
        Retorna el texto generado o None si falla.
        """
        if Client is None:
            return None
        space_url = os.environ.get("HF_SPACE_URL", "").strip()
        hf_token = os.environ.get("HF_TOKEN", "").strip()
        if not space_url:
            return None
        try:
            client = Client(space_url, hf_token=hf_token or None)
            result = client.predict(
                prompt,
                api_name="/predict",
            )
            if isinstance(result, str):
                text = result.strip()
            else:
                text = json.dumps(result, ensure_ascii=False)
            return text if text else None
        except Exception:
            return None

    def _call_colab(self, prompt: str) -> Optional[str]:
        """
        Envía un prompt a un servidor propio desplegado en Colab/Ngrok.
        Usa la configuracion almacenada en ame_nube.json.
        """
        config = _load_colab_config()
        if not config or not config.get("activo"):
            return None
        base_url = (config.get("servidor_general") or config.get("servidor_codigo") or "").strip()
        if not base_url:
            return None
        try:
            res = requests.post(
                f"{base_url}/v1/chat/completions",
                json={
                    "model": config.get(
                        "model_general", config.get("model_codigo", "rocinante-12b-uncensored")
                    ),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                },
                headers={"Content-Type": "application/json"},
                timeout=60.0,
            )
            if res.status_code == 200:
                try:
                    data = res.json()
                except ValueError:
                    return None
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content and str(content).strip():
                    return str(content).strip()
        except requests.Timeout:
            pass
        except requests.ConnectionError:
            pass
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────
    # Testing y Verificación
    # ──────────────────────────────────────────

    def test_provider_connection(self, provider_name: str) -> Dict[str, Any]:
        """
        Prueba la conexión a un proveedor específico.

        Retorna:
        {
            "provider": "...",
            "status": "ok" | "error" | "no_key",
            "latency_ms": float | None,
            "error": "..." (si aplica)
        }

        ⚠️ NO expone las API keys en el retorno.
        """
        import time

        if provider_name not in CLOUD_PROVIDERS:
            return {
                "provider": provider_name,
                "status": "error",
                "error": f"Provider '{provider_name}' not found",
            }

        cfg = CLOUD_PROVIDERS[provider_name]
        api_key = os.environ.get(cfg["api_key_env"])

        if not api_key:
            return {
                "provider": provider_name,
                "status": "no_key",
                "error": f"Missing {cfg['api_key_env']}",
            }

        # Prueba simple: "ping" de IA
        test_prompt = "Responde solo con 'OK' en una palabra."
        start = time.time()

        try:
            response = self._call_cloud(provider_name, cfg, test_prompt)
            latency = (time.time() - start) * 1000

            if response:
                return {
                    "provider": provider_name,
                    "status": "ok",
                    "latency_ms": round(latency, 2),
                    "model": cfg.get("model"),
                }
            else:
                return {
                    "provider": provider_name,
                    "status": "error",
                    "error": "No response from API",
                    "latency_ms": round(latency, 2),
                }
        except Exception as e:
            latency = (time.time() - start) * 1000
            return {
                "provider": provider_name,
                "status": "error",
                "error": f"Connection failed: {type(e).__name__}",
                "latency_ms": round(latency, 2),
            }

    def test_all_providers(self) -> Dict[str, Any]:
        """
        Prueba la conexión a TODOS los proveedores disponibles.

        Retorna resumen de disponibilidad y latencias.
        ⚠️ NO expone las API keys.
        """
        results = {
            "timestamp": str(__import__("datetime").datetime.now()),
            "providers": {},
            "summary": {
                "total": 0,
                "available": 0,
                "no_key": 0,
                "failed": 0,
            },
        }

        # Probar Ollama primero
        if self._is_ollama_available():
            results["providers"]["ollama"] = {
                "status": "ok",
                "type": "local",
                "model": DEFAULT_MODEL,
            }
            results["summary"]["available"] += 1
        else:
            results["providers"]["ollama"] = {
                "status": "error",
                "type": "local",
                "error": "Not running",
            }
            results["summary"]["failed"] += 1

        # Probar proveedores cloud en orden de failover
        for provider_name, _ in FAILOVER_ORDER:
            results["summary"]["total"] += 1
            test_result = self.test_provider_connection(provider_name)
            results["providers"][provider_name] = test_result

            if test_result["status"] == "ok":
                results["summary"]["available"] += 1
            elif test_result["status"] == "no_key":
                results["summary"]["no_key"] += 1
            else:
                results["summary"]["failed"] += 1

        return results

    # ──────────────────────────────────────────
    # Integración con Core Log y VOID
    # ──────────────────────────────────────────

    def query_void(self, query: str) -> List[Dict]:
        """
        Consulta la memoria VOID antes de responder.
        Útil para que AURA recuerde notas previas.
        """
        try:
            from void import search_void

            return search_void(query)
        except Exception:
            return []

    def route_and_log(self, prompt: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Enruta el prompt al modelo adecuado Y guarda una nota
        en knowledge_base si el contenido es relevante.
        """
        result = self.route(prompt, context)

        # Si el prompt parece una observación/nota relevante, guardarla
        core_log_keywords = [
            "observación",
            "observacion",
            "nota",
            "recuerda",
            "importante",
            "recordar",
            "apunta",
            "guarda esto",
        ]
        prompt_lower = prompt.lower()
        should_log = any(kw in prompt_lower for kw in core_log_keywords)

        if should_log:
            try:
                from core_log import save_note

                save_note(
                    content=prompt,
                    tags=[result.get("task_type", "general"), "ai_router"],
                    source="ai_router",
                    sync_firebase=True,
                )
                result["note_saved"] = True
            except Exception:
                result["note_saved"] = False

        return result


# ── Bloque de prueba ──
if __name__ == "__main__":
    import json

    router = AuraCognitiveRouter()

    print("=" * 70)
    print("🧠 AURA Cognitive Router v4 — Sistema de Failover Activado")
    print("=" * 70)
    print()

    # Test 1: Listar proveedores disponibles
    print("📋 PROVEEDORES DISPONIBLES:")
    providers = router.list_available_providers()
    for p in providers:
        print(f"   ✓ {p['name']}")
    print()

    # Test 2: Probar todas las conexiones
    print("🔍 VERIFICANDO CONEXIONES A TODOS LOS PROVEEDORES...")
    print("-" * 70)
    test_results = router.test_all_providers()

    print(f"   Ollama Local: ", end="")
    ollama_status = test_results["providers"].get("ollama", {}).get("status")
    print(f"{'✓ OK' if ollama_status == 'ok' else '✗ NO DISPONIBLE'}")
    print()

    print("   APIs Cloud (Orden de Failover):")
    for provider_name, provider_cfg in FAILOVER_ORDER:
        result = test_results["providers"].get(provider_name, {})
        status = result.get("status")

        if status == "ok":
            latency = result.get("latency_ms", "?")
            print(f"      {provider_cfg['priority']}. {provider_cfg['name']}: ✓ OK ({latency}ms)")
        elif status == "no_key":
            print(f"      {provider_cfg['priority']}. {provider_cfg['name']}: ⚠ Sin API Key")
        elif (
            provider_name == "hf_cloud"
            and result.get("error") == "ERROR_CONFIG: HF_TOKEN no configurado en .env"
        ):
            print(
                f"      {provider_cfg['priority']}. {provider_cfg['name']}: ⚠ Sin HF_TOKEN en .env"
            )
        else:
            print(f"      {provider_cfg['priority']}. {provider_cfg['name']}: ✗ Error")

    print()
    summary = test_results["summary"]
    print(
        f"   Resumen: {summary['available']} disponibles, "
        f"{summary['no_key']} sin clave, "
        f"{summary['failed']} fallidos"
    )
    print()

    # Test 3: Prueba de ruteo básico
    print("-" * 70)
    print("🧪 PRUEBA DE RUTEO:")
    test_prompts = [
        ("Escribe un script en Python", "code"),
        ("Explica paso a paso cómo funciona", "reasoning"),
        ("Responde rápidamente", "fast"),
    ]

    for prompt, expected_task in test_prompts:
        task = router._detect_task_type(prompt)
        model = router._get_best_model(prompt)
        print(f"   '{prompt[:40]}...'")
        print(f"      → Tarea: {task} (esperado: {expected_task})")
        print(f"      → Modelo: {model}")
    print()

    print("=" * 70)
    print("✅ CONFIGURACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 70)
