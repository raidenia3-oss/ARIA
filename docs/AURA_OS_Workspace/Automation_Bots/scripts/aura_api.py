from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import asyncio
import os
import json
import time
import base64
from pathlib import Path

from AURA_Core.brain_with_tools import AuraBrain
from AURA_Core.vector_memory import get_vector_memory
from AURA_Core.analytics import (
    init_db as analytics_init_db,
    record as analytics_record,
    dashboard as analytics_dashboard,
)

app = FastAPI(title="AURA API", version="4.1")

analytics_init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = AuraBrain()


class ChatRequest(BaseModel):
    message: str
    session_id: int | None = None
    persona: str | None = None
    provider: str | None = None
    tool_authorized: dict | None = None


class ShellAuthRequest(BaseModel):
    session_id: int
    command: str
    granted: bool


class IngestTextRequest(BaseModel):
    text: str
    source: str | None = None


class AnalyzeImageRequest(BaseModel):
    image_base64: str
    prompt: str
    session_id: int | None = None
    persona: str | None = None
    provider: str | None = None


class TranscribeRequest(BaseModel):
    prompt: str | None = None
    session_id: int | None = None
    persona: str | None = None


class AgentDebateRequest(BaseModel):
    topic: str


async def _call_gemini_vision(image_base64: str, prompt: str) -> dict:
    """Llama a Gemini 1.5 Flash para análisis de imagen."""
    try:
        import requests

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return {"error": "GEMINI_API_KEY no configurada"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": image_base64,
                            }
                        },
                    ]
                }
            ]
        }

        resp = requests.post(url, json=payload, timeout=60)
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        )
        return {
            "response": text or "(Sin respuesta de Gemini)",
            "provider_used": "gemini-2.0-flash",
        }
    except Exception as e:
        return {"error": str(e)}


async def _call_lm_studio_vision(image_base64: str, prompt: str) -> dict:
    """Intenta análisis de imagen en LM Studio local (para modelos con visión como Qwen2-VL)."""
    try:
        import requests

        url = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": os.getenv("LM_STUDIO_MODEL", "qwen2-vl-7b-instruct"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "response": text or "(Sin respuesta de LM Studio)",
            "provider_used": "lm-studio-local",
        }
    except Exception as e:
        return {"error": str(e), "fallback": True}


@app.post("/analyze-image")
async def analyze_image(req: AnalyzeImageRequest):
    """Analiza una imagen (base64) con un modelo de visión, con failover a Gemini."""
    try:
        # Intentar LM Studio primero (modelos locales con visión)
        result = await _call_lm_studio_vision(req.image_base64, req.prompt)
        if result.get("error") and not result.get("fallback"):
            # Si falló y no tiene fallback, retornar error
            return JSONResponse(result, status_code=500)
        if result.get("error") and result.get("fallback"):
            # LM Studio no disponible, usar Gemini como fallback
            result = await _call_gemini_vision(req.image_base64, req.prompt)

        if "error" in result and "Gemini" not in result.get("error", ""):
            return JSONResponse(result, status_code=500)

        # Si hay session_id, guardar en historial
        sid = req.session_id or brain.create_session(title="Vision Session")
        brain.get_history(sid, limit=1)  # Asegurar que existe

        return JSONResponse(
            {
                "session_id": sid,
                "response": result.get("response", ""),
                "provider_used": result.get("provider_used", "unknown"),
            }
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    session_id: int | None = Form(None),
    persona: str | None = Form(None),
):
    """Transcribe un archivo de audio corto (.wav, .mp3, .webm, .ogg) usando Groq Whisper o Gemini."""
    try:
        import requests

        # Leer archivo
        audio_bytes = await file.read()
        if not audio_bytes:
            return JSONResponse({"error": "Archivo vacío"}, status_code=400)

        # Intentar Groq Whisper primero (ultra-rápido)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                url = "https://api.groq.com/openai/v1/audio/transcriptions"
                headers = {"Authorization": f"Bearer {groq_key}"}
                files = {
                    "file": (
                        file.filename or "audio.wav",
                        audio_bytes,
                        file.content_type or "audio/wav",
                    )
                }
                data = {"model": "whisper-large-v3", "language": "es", "response_format": "json"}
                resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
                if resp.status_code == 200:
                    gd = resp.json()
                    text = gd.get("text", "")
                    if text:
                        sid = session_id or brain.create_session(title="Voice Session")
                        return JSONResponse(
                            {"session_id": sid, "transcription": text, "provider": "groq-whisper"}
                        )
            except Exception:
                pass  # Fallback a Gemini

        # Fallback a Gemini (Whisper via Gemini)
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                b64_audio = base64.b64encode(audio_bytes).decode()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt
                                    or "Transcribe este audio a texto plano en español."
                                },
                                {
                                    "inlineData": {
                                        "mimeType": file.content_type or "audio/wav",
                                        "data": b64_audio,
                                    }
                                },
                            ]
                        }
                    ]
                }
                resp = requests.post(url, json=payload, timeout=60)
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
                if text:
                    sid = session_id or brain.create_session(title="Voice Session")
                    return JSONResponse(
                        {"session_id": sid, "transcription": text, "provider": "gemini-whisper"}
                    )
            except Exception:
                pass

        return JSONResponse(
            {"error": "No se pudo transcribir. Verifica GROQ_API_KEY o GEMINI_API_KEY."},
            status_code=500,
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/analytics/dashboard")
async def analytics_dashboard_view():
    try:
        data = analytics_dashboard()
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    try:
        results = brain.router.test_all_providers()
        providers = {}
        for name, info in results.get("providers", {}).items():
            providers[name] = {
                "status": info.get("status"),
                "latency_s": info.get("latency_s"),
            }
        return {"status": "ok", "providers": providers}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/sessions")
async def list_sessions(limit: int = 50):
    try:
        history = brain.get_history(limit=limit)
        sessions = {}
        for msg in history:
            sid = msg.get("session_id")
            if sid is None:
                continue
            sessions.setdefault(sid, []).append(msg)
        items = []
        for sid, msgs in sessions.items():
            items.append(
                {
                    "session_id": sid,
                    "messages_count": len(msgs),
                    "last_role": msgs[-1].get("role"),
                    "last_ts": msgs[-1].get("ts"),
                }
            )
        return {"sessions": items}
    except Exception as e:
        return {"sessions": [], "error": str(e)}


@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start) * 1000
    try:
        route = request.url.path
        if route in ("/chat", "/agent-debate", "/swarm-review"):
            provider = ""
            model = ""
            input_tokens = 0
            output_tokens = 0
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.json()
                    provider = body.get("provider") or body.get("provider_used") or ""
                    model = body.get("model") or ""
                except Exception:
                    pass
            analytics_record(
                provider=provider,
                model=model,
                latency_ms=elapsed_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                endpoint=route,
            )
    except Exception:
        pass
    return response


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        if req.persona:
            brain.set_persona(req.persona)

        sid = req.session_id
        if sid is None:
            sid = brain.create_session(title="API Session")

        force_provider = req.provider or None
        tool_authorized = req.tool_authorized or None

        # RAG: buscar contexto relevante en ChromaDB e inyectarlo
        try:
            vm = get_vector_memory()
            rag_hits = vm.search_similar(req.message, limit=3)
            rag_context = ""
            if rag_hits:
                fragments = []
                for hit in rag_hits:
                    fragments.append(hit["text"])
                rag_context = (
                    "\n--- Contexto del proyecto (ChromaDB) ---\n"
                    + "\n\n".join(fragments)
                    + "\n--- Fin contexto ---\n"
                )
        except Exception:
            rag_context = ""

        # Inyectar contexto en el prompt si hay RAG hits
        augmented_prompt = req.message
        if rag_context:
            augmented_prompt = (
                "Informacion adicional del proyecto que debes usar si es relevante:\n"
                + rag_context
                + "\nPregunta del usuario:\n"
                + req.message
            )

        result = brain.process_input(
            session_id=sid,
            user_prompt=augmented_prompt,
            force_provider=force_provider,
            tool_authorized=tool_authorized,
        )

        payload = {
            "session_id": result.get("session_id"),
            "response": result.get("response"),
            "provider_used": result.get("provider_used"),
            "intention": result.get("intention"),
            "tool_used": result.get("tool_used"),
            "tool_output": result.get("tool_output"),
            "tool_pending": result.get("tool_pending"),
            "tool_risky": result.get("tool_risky"),
            "rag_used": bool(rag_context),
        }
        return JSONResponse(payload)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/ingest-text")
async def ingest_text(req: IngestTextRequest):
    """Recibe texto plano, lo chunktea y lo guarda en ChromaDB."""
    try:
        vm = get_vector_memory()
        metadata = {"source": req.source or "manual"}
        result = vm.add_document(req.text, metadata=metadata)
        return JSONResponse(
            {
                "status": "ok",
                "doc_id": result["doc_id"],
                "chunks": result["chunks"],
                "total_chars": result["total_chars"],
                "total_in_db": vm.count(),
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/knowledge/stats")
async def knowledge_stats():
    """Retorna estadisticas de la base de conocimiento."""
    try:
        vm = get_vector_memory()
        return {"total_entries": vm.count()}
    except Exception as e:
        return {"total_entries": 0, "error": str(e)}


@app.post("/agent-debate")
async def agent_debate(req: AgentDebateRequest):
    """Dispara el modo debate multi-agente sobre un tema."""
    try:
        from AURA_Core.tools import run_agent_debate

        result = run_agent_debate(req.topic)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/shell/authorize")
async def shell_authorize(req: ShellAuthRequest):
    try:
        tool_authorized = {"granted": req.granted, "command": req.command}
        history = brain.get_history(req.session_id, limit=10)
        user_prompt = ""
        for m in reversed(history):
            if m.get("role") == "user":
                user_prompt = m.get("content", "")
                break

        result = brain.process_input(
            session_id=req.session_id,
            user_prompt=user_prompt,
            tool_authorized=tool_authorized,
        )
        return JSONResponse(
            {
                "status": "ok",
                "response": result.get("response"),
                "tool_output": result.get("tool_output"),
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
