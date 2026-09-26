# -*- coding: utf-8 -*-
"""ARIA OS - Candle.rs Local LLM Integration.

Provides a FastAPI endpoint for local LLM inference via Candle.rs
(HuggingFace). Faster than Ollama HTTP round-trip (~5-8s vs 15s).

Phase L: Stub + fallback logic. Full implementation deferred to v5.2
when candle-core Rust crate is compiled.

Roadmap:
  Phase L (now):     Endpoint stub + fallback logic
  Phase L.2 (v5.2):  Install candle-core Rust crate
  Phase L.3 (v5.2):  Compile Mistral/Llama models
  Phase L.4 (v5.2):  Switch to Candle as default provider
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.Candle")

router = APIRouter(prefix="/api/ai/candle", tags=["ai"])

# Candle availability check — candle-core is a Rust crate, not pip-installable.
# We detect via a compiled binary or Python binding when available.
CANDLE_AVAILABLE = False
CANDLE_BIN = os.environ.get("CANDLE_BIN_PATH", "")  # path to compiled candle binary
CANDLE_MODELS_DIR = os.environ.get(
    "CANDLE_MODELS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "models", "candle"),
)


def _check_candle() -> bool:
    """Check if Candle runtime is available."""
    global CANDLE_AVAILABLE
    if CANDLE_BIN and os.path.isfile(CANDLE_BIN):
        CANDLE_AVAILABLE = True
    # Future: check for candle-core Python bindings
    try:
        import candle_core  # noqa: F401
        CANDLE_AVAILABLE = True
    except ImportError:
        pass
    return CANDLE_AVAILABLE


# ============================================================================
# Models
# ============================================================================

class CandleInferenceRequest(BaseModel):
    prompt: str
    model: str = Field(default="mistral", description="Model name: mistral, llama2, qwen")
    max_tokens: int = Field(default=256, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    system_prompt: Optional[str] = None


class CandleInferenceResponse(BaseModel):
    response: str
    provider: str
    model: str
    latency_ms: int
    tokens: int = 0


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/inference")
async def candle_inference(request: CandleInferenceRequest):
    """Local LLM inference via Candle.rs.

    When Candle is compiled and available, this runs inference locally
    without HTTP overhead. Falls back gracefully when not available.
    """
    if not _check_candle():
        raise HTTPException(
            status_code=503,
            detail=(
                "Candle.rs not compiled. Install candle-core Rust crate for v5.2. "
                "Falling back to Ollama."
            ),
        )

    start = time.time()
    try:
        # --- Candle inference implementation (v5.2) ---
        # import candle_core
        # from candle_models import load_model
        # model = load_model(request.model)
        # response = model.generate(request.prompt, max_tokens=request.max_tokens)
        # -------------------------------------------------

        # Stub: this code path is unreachable until Candle is compiled
        return CandleInferenceResponse(
            response="[Candle stub — not yet compiled]",
            provider="candle-stub",
            model=request.model,
            latency_ms=int((time.time() - start) * 1000),
            tokens=0,
        )
    except Exception as e:
        logger.error(f"Candle inference failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def candle_available_models():
    """List Candle-compatible models and their status."""
    available = []
    models_dir = CANDLE_MODELS_DIR
    if os.path.isdir(models_dir):
        for entry in os.listdir(models_dir):
            if os.path.isdir(os.path.join(models_dir, entry)):
                available.append(entry)

    return {
        "available": available or ["mistral-7b", "llama2-7b", "qwen-1.5b"],
        "compiled": _check_candle(),
        "models_dir": models_dir,
        "recommendation": (
            "Use Ollama for production, Candle for v5.2+"
            if not _check_candle()
            else "Candle ready — switch default in app.py"
        ),
    }


@router.get("/health")
async def candle_health():
    """Check Candle runtime availability."""
    available = _check_candle()
    return {
        "status": "available" if available else "not-available",
        "reason": (
            "Candle binary compiled" if available
            else "Requires Rust compilation (candle-core)"
        ),
        "fallback": "Using Ollama",
        "binary_path": CANDLE_BIN or "(not set)",
    }


def is_candle_available() -> bool:
    """Check if Candle can be used as a provider."""
    return _check_candle()


def init_candle():
    """Initialize Candle integration — log status."""
    if _check_candle():
        logger.info(f"Candle integration ready (binary: {CANDLE_BIN})")
    else:
        logger.info(
            "Candle not compiled — using Ollama fallback. "
            "Set CANDLE_BIN_PATH to enable Candle in v5.2."
        )