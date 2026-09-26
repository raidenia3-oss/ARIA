#!/usr/bin/env python3
"""
AURA Model Server — Sirve el modelo Qwen2.5 entrenado vía API compatible con OpenAI.

API endpoints (OpenAI-compatible):
  GET  /health               — health check + model info
  GET  /v1/models            — lista modelos disponibles
  POST /v1/chat/completions  — chat con el modelo local
  POST /v1/embeddings        — embeddings (si soporta)

Config:
  MODEL_PATH=models/qwen-1.5b   (ruta del modelo base o fine-tuneado)
  HOST=0.0.0.0
  PORT=8001

La app móvil se conecta a esta API en la red local.
Ejemplo: http://<IP_PC>:8001/v1/chat/completions
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import argparse
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AuraModelServer")

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODEL = os.getenv("MODEL_PATH", "models/qwen-1.5b")
HOST = os.getenv("MODEL_HOST", "0.0.0.0")
PORT = int(os.getenv("MODEL_PORT", "8001"))


class ModelServer:
    """
    Servidor de modelo con API compatible OpenAI.
    Soporta carga diferida, inferencia síncrona y async.
    """

    def __init__(self, model_path: str, max_context: int = 2048):
        self.model_path = model_path
        self.max_context = max_context
        self.tokenizer = None
        self.model = None
        self.device = None
        self._loaded = False
        self._lock = threading.Lock()
        self._model_info: Dict[str, Any] = {}

    def _load(self) -> bool:
        """Carga diferida del modelo (lazy loading)."""
        if self._loaded:
            return True

        with self._lock:
            if self._loaded:
                return True

            logger.info(f"Loading model: {self.model_path}")
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"Device: {self.device}")

            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path, trust_remote_code=True
            )
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            kwargs: Dict[str, Any] = {
                "trust_remote_code": True,
                "device_map": "auto" if self.device.type == "cuda" else None,
                "torch_dtype": torch.float16 if self.device.type == "cuda" else torch.float32,
            }

            # Use low_cpu_mem_usage on CPU
            if self.device.type == "cpu":
                kwargs["low_cpu_mem_usage"] = True

            self.model = AutoModelForCausalLM.from_pretrained(self.model_path, **kwargs)
            self.model.eval()

            # Model metadata
            params = sum(p.numel() for p in self.model.parameters())
            self._model_info = {
                "model": "qwen-2.5",
                "model_path": self.model_path,
                "params": params,
                "device": str(self.device),
                "max_context": self.max_context,
                "loaded_at": datetime.now().isoformat(),
            }

            self._loaded = True
            logger.info(f"Model loaded: {params:,} params on {self.device}")
            return True

    def is_loaded(self) -> bool:
        return self._loaded

    def get_info(self) -> Dict[str, Any]:
        """Devuelve información del modelo."""
        if not self._loaded:
            return {"loaded": False, "model_path": self.model_path}

        import torch
        return {
            "loaded": True,
            "model": self._model_info,
            "torch_cuda_available": torch.cuda.is_available(),
        }

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Genera respuesta con el modelo (OpenAI-compatible)."""
        import torch

        if not self._loaded:
            if not self._load():
                return {"error": "Failed to load model"}

        # Format as chat
        prompt = self._format_chat(messages)

        # Tokenize
        inputs = self.tokenizer(
            prompt, return_tensors="pt", truncation=True, max_length=self.max_context
        )
        if self.device.type == "cuda":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate
        start = time.time()
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True if temperature > 0 else False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        generated = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        response_text = generated[len(prompt):].strip()

        # Apply stop sequences
        if stop:
            for s in stop:
                idx = response_text.find(s)
                if idx != -1:
                    response_text = response_text[:idx].strip()

        elapsed = time.time() - start
        tokens = len(inputs["input_ids"][0]) + len(outputs[0]) - len(inputs["input_ids"][0])

        return {
            "id": f"aura-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "qwen-2.5",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(inputs["input_ids"][0]),
                "completion_tokens": tokens,
                "total_tokens": len(inputs["input_ids"][0]) + tokens,
            },
            "latency_ms": round(elapsed * 1000),
        }

    def _format_chat(self, messages: List[Dict[str, str]]) -> str:
        """Formatea mensajes como prompt de chat para Qwen."""
        parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        parts.append("Assistant:")
        return "\n".join(parts)


# ---------------------------------------------------------------------- #
#  FastAPI Server
# ---------------------------------------------------------------------- #
def create_app(model_path: str = DEFAULT_MODEL) -> Any:
    """Crea la aplicación FastAPI con el servidor de modelo."""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from typing import Optional

    app = FastAPI(
        title="AURA Model Server",
        description="Modelo Qwen2.5 local con API compatible OpenAI",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    server = ModelServer(model_path=model_path)

    class ChatMessage(BaseModel):
        role: str = Field(..., description="user, assistant, or system")
        content: str = Field(..., description="Message content")

    class ChatCompletionRequest(BaseModel):
        model: Optional[str] = None
        messages: List[ChatMessage]
        temperature: Optional[float] = 0.7
        max_tokens: Optional[int] = 512
        top_p: Optional[float] = 0.9
        stop: Optional[List[str]] = None
        stream: Optional[bool] = False

    @app.get("/health")
    async def health():
        info = server.get_info()
        return {
            "status": "ok" if server.is_loaded() or True else "loading",
            "service": "aura-model-server",
            "version": "1.0.0",
            "model_path": model_path,
            "model_info": info,
        }

    @app.get("/v1/models")
    async def list_models():
        return {
            "object": "list",
            "data": [
                {
                    "id": "qwen-2.5-1.5b",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "aura",
                    "permission": [],
                    "root": model_path,
                }
            ],
        }

    @app.get("/")
    async def root():
        return {
            "service": "AURA Model Server",
            "endpoints": ["/health", "/v1/models", "/v1/chat/completions", "/v1/embeddings"],
            "model": model_path,
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest):
        if not server.is_loaded():
            # Lazy load on first request
            logger.info("Lazy loading model on first request...")
            if not server._load():
                raise HTTPException(status_code=500, detail="Failed to load model")

        result = server.generate(
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 512,
            top_p=request.top_p or 0.9,
            stop=request.stop,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        logger.info(
            f"Chat: {len(request.messages)} msgs, "
            f"{result['usage']['total_tokens']} tokens, "
            f"{result['latency_ms']}ms"
        )
        return result

    return app


def main():
    parser = argparse.ArgumentParser(description="AURA Model Server")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Path to model")
    parser.add_argument("--host", default=HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=PORT, help="Bind port")
    args = parser.parse_args()

    # Pre-load model (optional — can be lazy)
    logger.info(f"Starting AURA Model Server on {args.host}:{args.port}")
    logger.info(f"Model: {args.model}")

    try:
        import uvicorn
    except ImportError:
        logger.error("uvicorn not installed. Install with: pip install uvicorn")
        sys.exit(1)

    app = create_app(args.model)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
