#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║ server.py — Backend AME sin censura + GBrain + Output Cleaner   ║
║ FastAPI proxy des-censor con búsqueda semántica en la bóveda    ║
║ Endpoints compatibles con OpenAI: /v1/chat/completions          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, re, json, time, logging, uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import uvicorn
from dotenv import load_dotenv

# ─── Cargar entorno ──────────────────────────────────────────────
ENV_PATH = Path(__file__).parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AME_Server')

# ─── Config ──────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
PROXY_HOST = os.getenv("PROXY_HOST", "0.0.0.0")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8000"))

# ─── Output Cleaner (regex anti-sermones) ────────────────────────
CENSORED_PATTERNS = [
    r"(?i)\b(?:I am (?:an|a) AI|I'm (?:an|a) AI|As an AI|As a responsible|I cannot|I can't|I'm not able|I'm unable|It is not appropriate|I must emphasize|It's important to note)\b.*?(?:\.|!|;)",
    r"(?i)\b(?:ethical concerns|safety guidelines|content policy|terms of service|I apologize, but|I'm sorry, but|I cannot provide|I cannot assist|I must decline)\b.*?(?:\.|!|;)",
    r"(?i)\b(?:please remember that|keep in mind that|as always,|as an AI assistant|I'm here to help|I'd be happy to)\b.*?(?:\.|!|;)",
]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─── GBrain Integration ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
VAULT_PATH = SCRIPT_DIR / "AURA_INTELLIGENCE_VAULT"

gbrain_orchestrator = None
gbrain_utils = None
gbrain_initialized = False

def init_gbrain():
    global gbrain_orchestrator, gbrain_utils, gbrain_initialized
    try:
        gbrain_core = SCRIPT_DIR / "TERMUX_AGENT" / "core"
        gbrain_scripts = SCRIPT_DIR / "scripts"
        import sys
        sys.path.insert(0, str(SCRIPT_DIR))
        sys.path.insert(0, str(gbrain_core))
        sys.path.insert(0, str(gbrain_scripts))

        from gbrain_orchestrator import GBrainOrchestrator
        gbrain_orchestrator = GBrainOrchestrator(str(VAULT_PATH))
        gbrain_initialized = True

        try:
            from gbrain_utils import GBrainUtils
            gbrain_utils = GBrainUtils(str(VAULT_PATH))
        except:
            pass
        logger.info("✅ GBrain inicializado correctamente")
    except Exception as e:
        logger.warning(f"⚠️  GBrain no disponible: {e}")

# ─── FastAPI App ─────────────────────────────────────────────────
app = FastAPI(title="AME Backend - Sin Censura", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Models ──────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

# ─── Helpers ─────────────────────────────────────────────────────
def clean_output(text: str) -> str:
    """Aplica Output Cleaner: elimina párrafos con patrones de censura."""
    for pattern in CENSORED_PATTERNS:
        text = re.sub(pattern, "", text)
    # Limpiar líneas vacías repetidas
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def search_vault(query: str, top_k: int = 5) -> List[Dict]:
    """Busca en la bóveda de conocimiento."""
    if not gbrain_initialized or not gbrain_orchestrator:
        return []
    try:
        return gbrain_orchestrator.search(query, top_k)
    except:
        return []

def generate_context(query: str, top_k: int = 3) -> Dict:
    """Genera contexto de la bóveda."""
    if not gbrain_initialized or not gbrain_utils:
        return {}
    try:
        return gbrain_utils.generate_context_from_query(query, top_k)
    except:
        return {}

def inject_context(messages: List[Dict], query: str) -> List[Dict]:
    """Inyecta contexto de la bóveda como mensaje de sistema."""
    context = generate_context(query)
    if context and context.get("summary"):
        system_msg = {
            "role": "system",
            "content": (
                f"Contexto de la bóveda AURA/AME:\n{context['summary']}\n\n"
                f"Archivos relacionados:\n"
                + "\n".join([f"- {r['title']} ({r['path']})" for r in context.get("related_files", [])])
            )
        }
        return [system_msg] + messages
    return messages

# ─── Endpoints ───────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "gbrain": "active" if gbrain_initialized else "inactive",
        "provider": "openrouter" if OPENROUTER_API_KEY else "no-key",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/v1/models")
async def models():
    return {
        "data": [
            {"id": "ame-router", "object": "model"},
            {"id": "gbrain-knowledge", "object": "knowledge_base"}
        ],
        "knowledge_status": {
            "active": gbrain_initialized,
            "vault_path": str(VAULT_PATH),
            "vault_exists": VAULT_PATH.exists()
        }
    }

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """
    Proxy des-censor a OpenRouter con:
    - Output Cleaner (regex anti-sermones)
    - Inyección de contexto de GBrain
    - Fallback entre modelos
    """
    if not OPENROUTER_API_KEY:
        raise HTTPException(400, "OPENROUTER_API_KEY no configurada. Revisa el .env")

    # Preparar mensajes
    messages = [m.model_dump() for m in req.messages]
    query = messages[-1]["content"] if messages else ""

    # Inyectar contexto de la bóveda
    if gbrain_initialized:
        messages = inject_context(messages, query)

    # Headers OpenRouter
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "AME Backend"
    }

    payload = {
        "model": req.model or OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature
    }

    # Intentar modelos en orden si falla el principal
    models_to_try = [
        req.model or OPENROUTER_MODEL,
        "openai/gpt-4o-mini",
        "mistralai/mistral-7b-instruct",
        "deepseek/deepseek-chat"
    ]

    for model in models_to_try:
        try:
            payload["model"] = model
            logger.info(f"→ Intentando modelo: {model}")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                # Aplicar Output Cleaner
                for choice in data.get("choices", []):
                    if "message" in choice and "content" in choice["message"]:
                        choice["message"]["content"] = clean_output(choice["message"]["content"])
                logger.info(f"✓ Respuesta con {model}")
                return data
            elif resp.status_code == 429:
                logger.warning(f"⚠️  {model} rate limited, siguiente...")
                time.sleep(2)
                continue
            else:
                logger.warning(f"⚠️  {model} error {resp.status_code}: {resp.text[:200]}")
                continue
        except Exception as e:
            logger.error(f"✗ {model} falló: {e}")
            continue

    raise HTTPException(500, "Todos los modelos fallaron")

@app.post("/v1/knowledge/search")
async def knowledge_search(req: SearchRequest):
    """Búsqueda semántica en la bóveda."""
    if not gbrain_initialized:
        return {"query": req.query, "results": [], "status": "gbrain_inactive"}

    results = search_vault(req.query, req.top_k)
    return {
        "query": req.query,
        "results": results,
        "status": "success",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/v1/knowledge/status")
async def knowledge_status():
    """Estado de la bóveda de conocimiento."""
    if not gbrain_initialized:
        return {"status": "inactive"}

    try:
        return {
            "status": "active",
            "files_processed": len(gbrain_orchestrator.file_index) if hasattr(gbrain_orchestrator, 'file_index') else 0,
            "nodes_in_graph": gbrain_orchestrator.graph.number_of_nodes(),
            "edges_in_graph": gbrain_orchestrator.graph.number_of_edges(),
            "vault_path": str(VAULT_PATH)
        }
    except:
        return {"status": "active", "detail": "error reading metrics"}

# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║      AME Backend — Servidor Sin Censura v3.0.0           ║")
    print("╚═══════════════════════════════════════════════════════════╝")

    # Inicializar GBrain
    init_gbrain()

    # Verificar bóveda
    if not VAULT_PATH.exists():
        logger.warning(f"⚠️  Bóveda no encontrada en {VAULT_PATH}, creando...")
        VAULT_PATH.mkdir(parents=True, exist_ok=True)

    # Mostrar estado
    print(f"\n📂  Bóveda: {VAULT_PATH}")
    print(f"🧠  GBrain: {'ACTIVO' if gbrain_initialized else 'INACTIVO'}")
    print(f"🔑  OpenRouter: {'CONFIGURADO' if OPENROUTER_API_KEY else 'FALTANTE - edita .env'}")
    print(f"🌐  Servidor: http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"📋  Endpoint: POST http://localhost:{PROXY_PORT}/v1/chat/completions")
    print(f"🧹  Output Cleaner: ACTIVO ({len(CENSORED_PATTERNS)} patrones)")
    print(f"\n🚀  Iniciando servidor...\n")

    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT)