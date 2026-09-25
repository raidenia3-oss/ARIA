"""AURA AI Providers — unified interface for multiple AI backends.

Supported providers:
- Local: Ollama, llama.cpp, any OpenAI-compatible endpoint
- Cloud: Gemini, Groq, OpenRouter, Hugging Face
- Fallback: local rule-based responses

Usage:
    from ai_providers import AIProviderManager
    manager = AIProviderManager()
    response = manager.chat("Hello")
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional


class AIProviderManager:
    def __init__(self) -> None:
        self.providers: Dict[str, Dict[str, Any]] = {
            "ollama": {"available": False, "base_url": "http://localhost:11434", "model": "dolphin-2_6-phi-2", "priority": 1},
            "gemini": {"available": False, "api_key": "", "model": "gemini-2.0-flash", "priority": 3},
            "groq": {"available": False, "api_key": "", "model": "llama-3.3-70b-versatile", "priority": 4},
            "openrouter": {"available": False, "api_key": "", "model": "meta-llama/llama-4-maverick", "priority": 5},
            "huggingface": {"available": False, "api_key": "", "model": "google/gemma-2-9b-it", "priority": 6},
            "huggingface_free": {"available": False, "model": "Qwen/Qwen2.5-0.5B-Instruct", "priority": 7},
            "local_openai": {"available": False, "base_url": "", "model": "", "priority": 7},
            "local": {"available": True, "priority": 99},
        }
        self._detect_providers()
        self._history: List[Dict[str, Any]] = []
        self._usage = {"requests": 0, "tokens": 0, "providers_used": {}}
        self._circuit_breaker: Dict[str, Dict[str, Any]] = {}
        self._latency_history: Dict[str, List[float]] = {}
        self._migration_plan = {
            "phase_1_external_apis": ["gemini", "groq", "openrouter"],
            "phase_2_local_model": "Qwen/Qwen2.5-0.5B-Instruct",
            "phase_3_fine_tuned": "fine-tuned-ame",
            "fallback_chain": ["ollama", "huggingface_free", "gemini", "groq", "openrouter", "huggingface", "local_openai", "local"],
            "description": "Ollama local primero (dolphin-2_6-phi-2 sin censura), luego HF Inference API (free tier), luego APIs externas.",
        }

    def _detect_providers(self) -> None:
        env = os.environ
        if env.get("LOCAL_LFM_BASE_URL") or self._check_endpoint("http://localhost:11434"):
            self.providers["ollama"]["available"] = True
        if env.get("LOCAL_OPENAI_BASE_URL") and env.get("LOCAL_OPENAI_MODEL"):
            self.providers["local_openai"]["available"] = True
            self.providers["local_openai"]["base_url"] = env["LOCAL_OPENAI_BASE_URL"]
            self.providers["local_openai"]["model"] = env["LOCAL_OPENAI_MODEL"]
        if env.get("GEMINI_API_KEY"):
            self.providers["gemini"]["available"] = True
            self.providers["gemini"]["api_key"] = env["GEMINI_API_KEY"]
        if env.get("GROQ_API_KEY"):
            self.providers["groq"]["available"] = True
            self.providers["groq"]["api_key"] = env["GROQ_API_KEY"]
        if env.get("OPENROUTER_API_KEY"):
            self.providers["openrouter"]["available"] = True
            self.providers["openrouter"]["api_key"] = env["OPENROUTER_API_KEY"]
        if env.get("HF_TOKEN"):
            self.providers["huggingface"]["available"] = True
            self.providers["huggingface"]["api_key"] = env["HF_TOKEN"]
            self.providers["huggingface_free"]["available"] = True

    def _check_endpoint(self, url: str, timeout: int = 2) -> bool:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=timeout):
                return True
        except Exception:
            return False

    def _is_circuit_open(self, provider: str) -> bool:
        cb = self._circuit_breaker.get(provider)
        if not cb:
            return False
        if time.time() - cb["last_failure"] > 30:
            del self._circuit_breaker[provider]
            return False
        return cb["failures"] >= 3

    def _record_success(self, provider: str, latency: float) -> None:
        self._latency_history.setdefault(provider, []).append(latency)
        if len(self._latency_history[provider]) > 20:
            self._latency_history[provider].pop(0)
        if provider in self._circuit_breaker:
            del self._circuit_breaker[provider]

    def _record_failure(self, provider: str) -> None:
        cb = self._circuit_breaker.get(provider, {"failures": 0, "last_failure": 0})
        cb["failures"] += 1
        cb["last_failure"] = time.time()
        self._circuit_breaker[provider] = cb

    def get_available_providers(self) -> List[str]:
        return [name for name, info in self.providers.items() if info.get("available") and not self._is_circuit_open(name)]

    def get_best_provider(self) -> Optional[str]:
        available = self.get_available_providers()
        if not available:
            return "local"
        return sorted(available, key=lambda p: self.providers[p].get("priority", 99))[0]

    def get_provider_health(self) -> Dict[str, Any]:
        health = {}
        for name in self.providers:
            latencies = self._latency_history.get(name, [])
            avg_latency = sum(latencies) / len(latencies) if latencies else None
            health[name] = {
                "available": self.providers[name].get("available", False),
                "circuit_open": self._is_circuit_open(name),
                "avg_latency": avg_latency,
                "failures": self._circuit_breaker.get(name, {}).get("failures", 0),
            }
        return health

    def get_migration_plan(self) -> Dict[str, Any]:
        return dict(self._migration_plan)

    def ping(self) -> bool:
        """Comprueba si el servidor Ollama responde (para el launcher/HUD)."""
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3):
                return True
        except Exception:
            return False

    def list_ollama_models(self) -> List[str]:
        """Lista los modelos instalados en Ollama local."""
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                data = json.loads(r.read())
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def refresh_ollama(self) -> Dict[str, Any]:
        """Re-detecta Ollama en vivo y sincroniza modelo activo con lo instalado."""
        try:
            models = self.list_ollama_models()
        except Exception:
            models = []
        online = self.ping() if hasattr(self, "ping") else bool(models)
        self.providers["ollama"]["available"] = bool(online)
        active = os.environ.get("LOCAL_LFM_MODEL", self.providers["ollama"].get("model", "dolphin-2_6-phi-2"))
        installed = (active in models or (active + ":latest") in models) if models else True
        if models and not installed:
            active = models[0]
            self.providers["ollama"]["model"] = active
        return {"online": online, "active": active, "models": models, "installed": installed}

    def chat_stream_ollama(self, message: str, history: Optional[List[List[str]]] = None, system_prompt: str = ""):
        """Generador: emite fragmentos de texto (streaming SSE) desde Ollama.

        Nota de implementación:
        urllib.request.urlopen responde con iterador de bytes por línea SSE
        (formato: '{\"_json...}\\n'). Para leer streaming de Ollama usamos una petición
        POST con `urllib.request.Request` y luego `urlopen` línea por línea; no
        confundir el módulo `urllib` con el submódulo `urllib.request`.
        """
        base = os.environ.get("LOCAL_LFM_BASE_URL", "http://localhost:11434")
        model = os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"model": model, "messages": messages, "stream": True}).encode("utf-8")
        req_url = f"{base}/api/chat"
        import urllib.request as _urlreq
        req = _urlreq.Request(req_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with _urlreq.urlopen(req, timeout=300) as r:
            buf = ""
            for raw in r:
                text_chunk = raw.decode("utf-8", "replace")
                buf += text_chunk
                # Ollama envía líneas JSON delimitadas por \\n; splitlines nos da cada línea
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lin = json.loads(line)
                    except Exception:
                        continue
                    # No hacer .strip() por token: Ollama antepone el espacio de cada
                    # palabra y eliminarlo concatenaría todas las palabras sin espacios.
                    content = (lin.get("message") or {}).get("content") or ""
                    if content.strip():
                        yield content
                    if lin.get("done"):
                        return
            last = buf.strip()
            if last:
                try:
                    lin = json.loads(last)
                except Exception:
                    return
                content = (lin.get("message") or {}).get("content") or ""
                if content.strip():
                    yield content

    def chat(self, message: str, history: Optional[List[List[str]]] = None, system_prompt: str = "", provider: Optional[str] = None) -> Dict[str, Any]:
        if provider is None:
            provider = self.get_best_provider()
        start = time.time()
        try:
            if provider == "ollama" and not self._is_circuit_open("ollama"):
                result = self._chat_ollama(message, history, system_prompt)
            elif provider == "gemini" and not self._is_circuit_open("gemini"):
                result = self._chat_gemini(message, history, system_prompt)
            elif provider == "groq" and not self._is_circuit_open("groq"):
                result = self._chat_groq(message, history, system_prompt)
            elif provider == "openrouter" and not self._is_circuit_open("openrouter"):
                result = self._chat_openrouter(message, history, system_prompt)
            elif provider == "huggingface" and not self._is_circuit_open("huggingface"):
                result = self._chat_huggingface(message, history, system_prompt)
            elif provider == "huggingface_free" and not self._is_circuit_open("huggingface_free"):
                result = self._chat_huggingface_free(message, history, system_prompt)
            elif provider == "local_openai" and not self._is_circuit_open("local_openai"):
                result = self._chat_local_openai(message, history, system_prompt)
            else:
                result = self._chat_local(message, history, system_prompt)
                result["provider"] = "local"
            latency = time.time() - start
            self._record_success(provider, latency)
            self._usage["requests"] += 1
            self._usage["providers_used"][provider] = self._usage["providers_used"].get(provider, 0) + 1
            result["provider"] = provider
            result["latency"] = round(latency, 2)
            self._history.append({"message": message, "response": result.get("message", ""), "provider": provider, "latency": latency})
            return result
        except Exception as exc:
            self._record_failure(provider)
            result = self._chat_local(message, history, system_prompt)
            result["provider"] = "local"
            result["error"] = str(exc)
            latency = time.time() - start
            result["latency"] = round(latency, 2)
            self._history.append({"message": message, "response": result.get("message", ""), "provider": "local", "latency": latency, "error": str(exc)})
            return result

    def _chat_local_openai(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        base = os.environ.get("LOCAL_OPENAI_BASE_URL", "").rstrip("/")
        model = os.environ.get("LOCAL_OPENAI_MODEL", "")
        if not base or not model:
            raise ValueError("LOCAL_OPENAI_BASE_URL y LOCAL_OPENAI_MODEL no configurados")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"model": model, "messages": messages, "stream": False, "temperature": 0.7}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        return {"message": text, "model": model, "finish_reason": "completed"}

    def _chat_ollama(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        base = os.environ.get("LOCAL_LFM_BASE_URL", "http://localhost:11434")
        model = os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2:latest")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(f"{base}/api/chat", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        text = ((data.get("message") or {}).get("content") or "").strip()
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        self._usage["tokens"] += tokens
        return {"message": text, "tokens": tokens}

    def _chat_gemini(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
            contents.append({"role": "model", "parts": [{"text": "Entendido."}]})
        if history:
            for h in history[-10:]:
                contents.append({"role": "user", "parts": [{"text": h[0]}]})
                if len(h) > 1 and h[1]:
                    contents.append({"role": "model", "parts": [{"text": h[1]}]})
        contents.append({"role": "user", "parts": [{"text": message}]})
        body = json.dumps({"contents": contents, "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        text = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts", [{}])[0].get("text", "")
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        self._usage["tokens"] += tokens
        return {"message": text.strip(), "tokens": tokens}

    def _chat_groq(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        api_key = os.environ.get("GROQ_API_KEY", "")
        model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)
        self._usage["tokens"] += tokens
        return {"message": text.strip(), "tokens": tokens}

    def _chat_openrouter(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        model = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-4-maverick")
        url = "https://openrouter.ai/api/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)
        self._usage["tokens"] += tokens
        return {"message": text.strip(), "tokens": tokens}

    def _chat_huggingface(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        api_key = os.environ.get("HF_TOKEN", "")
        model = os.environ.get("HF_MODEL", "google/gemma-2-9b-it")
        url = f"https://router.huggingface.co/hf-inference/models/{model}/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"messages": messages, "stream": False}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)
        self._usage["tokens"] += tokens
        return {"message": text.strip(), "tokens": tokens}

    def _chat_huggingface_free(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        model = os.environ.get("HF_FREE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
        url = f"https://router.huggingface.co/hf-inference/models/{model}/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            for h in history[-10:]:
                messages.append({"role": "user", "content": h[0]})
                if len(h) > 1 and h[1]:
                    messages.append({"role": "assistant", "content": h[1]})
        messages.append({"role": "user", "content": message})
        body = json.dumps({"messages": messages, "stream": False}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "")
        tokens = data.get("usage", {}).get("total_tokens", 0)
        self._usage["tokens"] += tokens
        return {"message": text.strip(), "tokens": tokens}

    def _web_search(self, query: str) -> Dict[str, Any]:
        try:
            import urllib.request
            import urllib.parse
            url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            results = []
            for line in html.splitlines():
                if "result__a" in line and "href=" in line:
                    results.append(line.strip())
                if len(results) >= 5:
                    break
            return {"results": results, "count": len(results)}
        except Exception as e:
            return {"results": [], "error": str(e)}

    def _chat_local(self, message: str, history: Optional[List[List[str]]], system_prompt: str) -> Dict[str, Any]:
        msg = message.strip()
        lower = msg.lower()
        if any(g in lower for g in ["hola", "buenas", "hello", "hi", "qué tal", "buenos días"]):
            return {"message": "Hola, soy AURA. ¿En qué puedo ayudarte?", "provider": "local"}
        if any(g in lower for g in ["como estas", "cómo estás", "como andas", "qué pasa"]):
            return {"message": "Estoy operativo. Listo para ayudarte con el proyecto AURA.", "provider": "local"}
        if any(g in lower for g in ["proyecto", "aura"]):
            return {"message": "AURA es un ecosistema multi-servicio: backend FastAPI, frontend Next.js, bot Discord, HF Space y app de escritorio.", "provider": "local"}
        if any(g in lower for g in ["backend", "fastapi", "api"]):
            return {"message": "El backend corre en el puerto 8000. Endpoints principales: /health, /api/hf-chat, /api/status, /api/logs.", "provider": "local"}
        if any(g in lower for g in ["frontend", "next", "react"]):
            return {"message": "El frontend es Next.js en el puerto 3000. Incluye chat, panel de control y tabs de servicios.", "provider": "local"}
        if any(g in lower for g in ["docker", "compose"]):
            return {"message": "Podés levantar todo con docker-compose up --build. O usar la app de escritorio aura_app.py.", "provider": "local"}
        if any(g in lower for g in ["error", "falla", "problema", "arreglar"]):
            return {"message": "Usá la pestaña Repair de la app de escritorio para escanear y reparar automáticamente el proyecto.", "provider": "local"}
        if any(g in lower for g in ["agente", "agent", "kilo", "cline"]):
            return {"message": "La pestaña Agents integra Kilo y Cline. Podés pedirles que escaneen y arreglen errores del proyecto.", "provider": "local"}
        if any(g in lower for g in ["desplegar", "deploy", "producción"]):
            return {"message": "Para producción usá docker-compose up --build. AURA soporta PostgreSQL y Redis en producción.", "provider": "local"}
        if any(g in lower for g in ["voz", "voice", "microfono", "micrófono"]):
            return {"message": "La pestaña Voice usa wake-word 'hey aura', STT y TTS. Requiere SpeechRecognition y pyttsx3.", "provider": "local"}
        if any(g in lower for g in ["gestos", "gesture", "mano", "cámara"]):
            return {"message": "La pestaña Gestures usa MediaPipe para tracking de manos. Clasifica: fist, index, peace, open_hand.", "provider": "local"}
        if any(g in lower for g in ["visión", "vision", "roi", "filtros"]):
            return {"message": "La pestaña Vision aplica filtros dinámicos dentro de un polígono definido por tu mano: cyan, thermal, ascii, dots, pixelate, edge.", "provider": "local"}
        if any(g in lower for g in ["osint", "investigación", "investigar", "buscar", "busqueda", "web", "internet", "noticias", "información", "informar"]):
            results = self._web_search(msg)
            if results.get("error"):
                return {"message": f"La pestaña OSINT incluye directorio de herramientas y generador de identidades sintéticas para testing. (Busqueda web falló: {results['error']})", "provider": "local"}
            count = results.get("count", 0)
            if count > 0:
                first = results["results"][0] if results["results"] else ""
                return {"message": f"Busqué '{msg}' en DuckDuckGo. Encontré {count} resultados. Para detalles completos, activá la pestaña OSINT o instalá Ollama para análisis más profundo. Primer resultado: {first[:200]}", "provider": "local"}
            return {"message": f"OSINT activo. Busqué '{msg}' pero no se encontraron resultados. Activá la pestaña OSINT para investigar con herramientas de identidad sintética, o instalá Ollama para respuestas más avanzadas.", "provider": "local"}
        if any(g in lower for g in ["youtube", "video", "shorts", "reel", "mirar", "ver video"]):
            if "youtube.com" in lower or "youtu.be" in lower:
                return {"message": "Reconocí un link de YouTube. Usá la pestaña Social Research (o POST /api/social-research/collect) para descargarlo, transcribirlo con Whisper y analizar el contenido. Requiere yt-dlp instalado.", "provider": "local"}
            return {"message": "Módulo Social Research disponible: descarga videos de YouTube/Instagram/TikTok con yt-dlp, transcribe audio con Whisper y analiza contenido. Activá la pestaña Social Research o instalá Ollama para IA conversacional.", "provider": "local"}
        if any(g in lower for g in ["entrenar", "train", "modelo"]):
            return {"message": "Entrenamiento disponible en la pestaña Training. Modelo por defecto: Qwen/Qwen2.5-1.5B-Instruct", "provider": "local"}
        if any(g in lower for g in ["logs", "registros", "bitácora"]):
            return {"message": "Logs disponibles en la pestaña Logs. Podés ver logs del backend y servicios.", "provider": "local"}
        if any(g in lower for g in ["status", "estado", "salud"]):
            return {"message": "Sistema activo. Backend, frontend, HF Space, Discord bot operativos. Módulos: Voice, Gestures, Vision, OSINT.", "provider": "local"}
        if any(g in lower for g in ["help", "ayuda", "comandos"]):
            return {"message": "Comandos: /help, /clear, /status, /stats, /services, /logs, /train, /voice, /gesture, /vision, /osint. También podés preguntar por cualquier módulo de AURA.", "provider": "local"}
        if msg.startswith("/"):
            return {"message": f"Comando '{msg}' reconocido. Funcionalidad en desarrollo.", "provider": "local"}
        return {"message": f"Recibido: '{msg}'. Sin modelo de IA activo. Instalá Ollama con `ollama pull dolphin-2_6-phi-2` para IA local sin censura, o configurá GEMINI_API_KEY / GROQ_API_KEY / LOCAL_OPENAI_BASE_URL + LOCAL_OPENAI_MODEL para alternativas.", "provider": "local"}

    def get_usage(self) -> Dict[str, Any]:
        return self._usage

    def get_history(self) -> List[Dict[str, Any]]:
        return self._history[-50:]
