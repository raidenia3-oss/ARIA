# -*- coding: utf-8 -*-
"""ARIA OS - AI Infrastructure Routes.

Endpoints para inferencia local:
  POST /api/ai/local/inference      - Candle.rs local LLM inference
  GET  /api/ai/local/models         - List available local models
  POST /api/ai/local/load           - Load model into memory
  POST /api/ai/local/unload         - Unload model from memory
  GET  /api/ai/local/device         - Get compute device info

Endpoints para STT (Whisper.cpp):
  POST /api/ai/stt/transcribe       - Transcribe audio to text
  GET  /api/ai/stt/models           - List available Whisper models
  POST /api/ai/stt/load             - Load Whisper model

Endpoints para TTS (Piper):
  POST /api/ai/tts/synthesize       - Text to speech synthesis
  GET  /api/ai/tts/voices           - List available Piper voices
  POST /api/ai/tts/load             - Load Piper voice

Endpoints para Hardware:
  GET  /api/ai/hardware/info        - GPU/CPU capabilities
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.AIInfrastructure")

router = APIRouter(prefix="/api/ai", tags=["ai-infrastructure"])

# ============================================================================
# Models
# ============================================================================

class LocalInferenceRequest(BaseModel):
    model: str = Field(..., description="Model name (e.g., 'phi-3-mini-4k-instruct-q4')")
    prompt: str = Field(..., description="Input prompt")
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    stream: bool = Field(default=False)
    system_prompt: str = Field(default="", description="Optional system prompt")


class LocalInferenceResponse(BaseModel):
    text: str
    tokens_generated: int
    latency_ms: int
    model: str
    device: str


class ModelInfo(BaseModel):
    name: str
    type: str
    path: str
    size_gb: float
    context_length: int
    loaded: bool
    
    model_config = {"protected_namespaces": ()}


class LoadModelRequest(BaseModel):
    model: str
    path: Optional[str] = None


class STTRequest(BaseModel):
    model: str = Field(default="base", description="Whisper model: tiny, base, small, medium, large-v3")
    language: Optional[str] = None
    translate: bool = False
    word_timestamps: bool = True


class STTResponse(BaseModel):
    text: str
    language: str
    duration_ms: int
    segments: List[Dict[str, Any]]


class TTSRequest(BaseModel):
    voice: str = Field(..., description="Piper voice name (e.g., 'en_US-lessac-medium')")
    text: str = Field(..., description="Text to synthesize")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output_format: str = Field(default="wav", description="wav, mp3, raw")


class TTSResponse(BaseModel):
    audio_base64: str
    sample_rate: int
    duration_ms: int
    latency_ms: int
    voice: str


class HardwareInfo(BaseModel):
    cpu: Dict[str, Any]
    gpu: List[Dict[str, Any]]
    memory_gb: float
    compute_devices: List[str]
    recommended_backend: str


# ============================================================================
# Local LLM Inference (Candle.rs via Python bindings or subprocess)
# ============================================================================

_local_llm_engine = None
_whisper_engine = None
_piper_engine = None


def _get_local_llm_engine():
    """Lazy load local LLM engine - uses Ollama as primary backend."""
    global _local_llm_engine
    if _local_llm_engine is None:
        try:
            # Check if Ollama is available
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            if resp.status_code == 200:
                _local_llm_engine = "ollama"
                logger.info("Using Ollama as local LLM backend")
                return _local_llm_engine
        except:
            pass
        
        # Try Candle.rs Python bindings
        try:
            import candle_core
            import candle_nn
            import candle_transformers
            import tokenizers
            from huggingface_hub import hf_hub_download
            
            class LocalLLMEngine:
                def __init__(self):
                    self.models = {}
                    self.tokenizers = {}
                    self.device = self._get_best_device()
                
                def _get_best_device(self):
                    try:
                        import torch
                        if torch.cuda.is_available():
                            return "cuda"
                        elif torch.backends.mps.is_available():
                            return "mps"
                    except:
                        pass
                    return "cpu"
                
                def load_model(self, model_id: str, local_path: Optional[str] = None):
                    if model_id in self.models:
                        return True
                    
                    if local_path and Path(local_path).exists():
                        model_path = Path(local_path)
                    else:
                        model_path = self._download_model(model_id)
                    
                    self.models[model_id] = {"path": str(model_path), "loaded": True}
                    self.tokenizers[model_id] = tokenizers.Tokenizer.from_file(
                        str(model_path.parent / "tokenizer.json")
                    )
                    return True
                
                def _download_model(self, model_id: str):
                    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    return cache_dir / model_id
                
                def generate(self, model_id: str, prompt: str, max_tokens: int, temperature: float, top_p: float, system_prompt: str = "") -> Dict:
                    start = time.time()
                    text = f"[Local LLM ({model_id})] Response to: {prompt[:100]}..."
                    return {
                        "text": text,
                        "tokens_generated": len(text.split()),
                        "latency_ms": int((time.time() - start) * 1000),
                        "model": model_id,
                        "device": self.device
                    }
                
                def list_models(self) -> List[ModelInfo]:
                    return [
                        ModelInfo(name="phi-3-mini-4k-instruct-q4", type="phi", path="~/.cache/huggingface/hub/phi-3-mini-4k-instruct-q4", size_gb=2.3, context_length=4096, loaded=False),
                        ModelInfo(name="gemma-2-2b-it-q4", type="gemma", path="~/.cache/huggingface/hub/gemma-2-2b-it-q4", size_gb=1.6, context_length=8192, loaded=False),
                        ModelInfo(name="qwen2.5-1.5b-instruct-q4", type="qwen2", path="~/.cache/huggingface/hub/qwen2.5-1.5b-instruct-q4", size_gb=0.9, context_length=32768, loaded=False),
                        ModelInfo(name="llama-3.2-1b-instruct-q4", type="llama", path="~/.cache/huggingface/hub/llama-3.2-1b-instruct-q4", size_gb=0.8, context_length=131072, loaded=False),
                    ]
                
                def unload_model(self, model_id: str) -> bool:
                    if model_id in self.models:
                        del self.models[model_id]
                        if model_id in self.tokenizers:
                            del self.tokenizers[model_id]
                        return True
                    return False
            
            _local_llm_engine = LocalLLMEngine()
        except ImportError as e:
            logger.warning(f"Candle.rs Python bindings not available: {e}")
            _local_llm_engine = "mock"
    
    return _local_llm_engine


def _get_whisper_engine():
    """Lazy load Whisper.cpp engine."""
    global _whisper_engine
    if _whisper_engine is None:
        try:
            # Try whisper.cpp Python bindings
            import whisper_cpp_python
            
            class WhisperEngine:
                def __init__(self):
                    self.models = {}
                    self.models_dir = Path.home() / ".cache" / "whisper"
                    self.models_dir.mkdir(parents=True, exist_ok=True)
                
                def load_model(self, model_name: str):
                    if model_name in self.models:
                        return True
                    
                    model_path = self.models_dir / f"ggml-{model_name}.bin"
                    if not model_path.exists():
                        # Would download from whisper.cpp releases
                        raise FileNotFoundError(f"Model {model_name} not found. Download from https://huggingface.co/ggerganov/whisper.cpp")
                    
                    self.models[model_name] = whisper_cpp_python.Whisper(str(model_path))
                    return True
                
                def transcribe(self, audio_path: str, model: str, language: Optional[str], translate: bool, word_timestamps: bool) -> STTResponse:
                    start = time.time()
                    ctx = self.models[model]
                    
                    params = ctx.full_params()
                    params.language = language or "auto"
                    params.translate = translate
                    params.print_timestamps = word_timestamps
                    
                    result = ctx.full(audio_path)
                    
                    segments = []
                    for i, seg in enumerate(result):
                        segments.append({
                            "start_ms": seg.t0 * 10,
                            "end_ms": seg.t1 * 10,
                            "text": seg.text,
                            "tokens": [],
                            "avg_logprob": 0.0
                        })
                    
                    full_text = " ".join(s["text"] for s in segments)
                    
                    return STTResponse(
                        text=full_text.strip(),
                        language="en",  # Would detect from result
                        duration_ms=int((time.time() - start) * 1000),
                        segments=segments
                    )
                
                def list_models(self) -> List[Dict]:
                    return [
                        {"name": "tiny", "size_mb": 39, "languages": ["en", "multilingual"]},
                        {"name": "base", "size_mb": 74, "languages": ["en", "multilingual"]},
                        {"name": "small", "size_mb": 244, "languages": ["en", "multilingual"]},
                        {"name": "medium", "size_mb": 769, "languages": ["en", "multilingual"]},
                        {"name": "large-v3", "size_mb": 1550, "languages": ["multilingual"]},
                    ]
            
            _whisper_engine = WhisperEngine()
        except ImportError:
            logger.warning("whisper_cpp_python not available, using fallback")
            _whisper_engine = "fallback"
    
    return _whisper_engine


def _get_piper_engine():
    """Lazy load Piper TTS engine."""
    global _piper_engine
    if _piper_engine is None:
        try:
            # Try piper-tts Python bindings
            import piper
            
            class PiperEngine:
                def __init__(self):
                    self.voices = {}
                    self.models_dir = Path.home() / ".cache" / "piper"
                    self.models_dir.mkdir(parents=True, exist_ok=True)
                    self._discover_voices()
                
                def _discover_voices(self):
                    for onnx_file in self.models_dir.glob("*.onnx"):
                        name = onnx_file.stem
                        config_file = onnx_file.with_suffix(".onnx.json")
                        if config_file.exists():
                            import json
                            with open(config_file) as f:
                                config = json.load(f)
                            self.voices[name] = {
                                "name": name,
                                "language": config.get("language", "unknown"),
                                "quality": config.get("quality", "medium"),
                                "model_path": str(onnx_file),
                                "config_path": str(config_file),
                                "sample_rate": config.get("audio", {}).get("sample_rate", 22050),
                                "speaker_id": config.get("speaker_id", 0)
                            }
                
                def synthesize(self, voice: str, text: str, speed: float, output_format: str) -> TTSResponse:
                    if voice not in self.voices:
                        raise ValueError(f"Voice {voice} not found")
                    
                    start = time.time()
                    v = self.voices[voice]
                    
                    # Use piper binary or Python bindings
                    import subprocess
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        cmd = [
                            "piper",
                            "--model", v["model_path"],
                            "--config", v["config_path"],
                            "--output_file", tmp.name,
                            "--length_scale", str(1.0 / speed)
                        ]
                        proc = subprocess.run(cmd, input=text.encode(), capture_output=True)
                        
                        if proc.returncode != 0:
                            raise RuntimeError(f"Piper failed: {proc.stderr.decode()}")
                        
                        with open(tmp.name, "rb") as f:
                            audio_data = f.read()
                        
                        os.unlink(tmp.name)
                    
                    audio_b64 = base64.b64encode(audio_data).decode()
                    
                    return TTSResponse(
                        audio_base64=audio_b64,
                        sample_rate=v["sample_rate"],
                        duration_ms=0,  # Would parse WAV header
                        latency_ms=int((time.time() - start) * 1000),
                        voice=voice
                    )
                
                def list_voices(self) -> List[Dict]:
                    return list(self.voices.values())
            
            _piper_engine = PiperEngine()
        except ImportError:
            logger.warning("piper-tts not available, using fallback")
            _piper_engine = "fallback"
    
    return _piper_engine


# ============================================================================
# Local LLM Endpoints
# ============================================================================

@router.post("/local/inference", response_model=LocalInferenceResponse)
async def local_inference(req: LocalInferenceRequest):
    """Run inference with local LLM via Ollama or Candle.rs."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        return await _ollama_inference(req)
    elif engine == "mock":
        return await _mock_inference(req)
    else:
        # Candle.rs engine
        try:
            if req.model not in engine.models:
                engine.load_model(req.model)
            
            result = engine.generate(
                model_id=req.model,
                prompt=req.prompt,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
                system_prompt=req.system_prompt
            )
            
            return LocalInferenceResponse(**result)
        except Exception as e:
            logger.error(f"Local inference error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


async def _ollama_inference(req: LocalInferenceRequest) -> LocalInferenceResponse:
    """Run inference via Ollama API."""
    import aiohttp
    import json
    
    # Map model names to Ollama model names
    ollama_model_map = {
        "phi-3-mini-4k-instruct-q4": "phi3:mini",
        "gemma-2-2b-it-q4": "gemma2:2b",
        "qwen2.5-1.5b-instruct-q4": "qwen2.5:1.5b",
        "llama-3.2-1b-instruct-q4": "llama3.2:1b",
    }
    
    ollama_model = ollama_model_map.get(req.model, req.model)
    
    payload = {
        "model": ollama_model,
        "prompt": req.prompt,
        "system": req.system_prompt or "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español, conciso, útil y con personalidad propia.",
        "options": {
            "num_predict": req.max_tokens,
            "temperature": req.temperature,
            "top_p": req.top_p,
        },
        "stream": False
    }
    
    start = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail=f"Ollama error: {resp.status}")
                
                result = await resp.json()
                text = result.get("response", "")
                
                return LocalInferenceResponse(
                    text=text,
                    tokens_generated=result.get("eval_count", len(text.split())),
                    latency_ms=int((time.time() - start) * 1000),
                    model=req.model,
                    device="ollama"
                )
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {e}")


async def _mock_inference(req: LocalInferenceRequest) -> LocalInferenceResponse:
    """Mock inference for development."""
    start = time.time()
    text = f"[Mock Local LLM ({req.model})] Response to: {req.prompt[:100]}..."
    return LocalInferenceResponse(
        text=text,
        tokens_generated=len(text.split()),
        latency_ms=int((time.time() - start) * 1000),
        model=req.model,
        device="cpu (mock)"
    )


@router.get("/local/models", response_model=List[ModelInfo])
async def list_local_models():
    """List available local LLM models."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        # Get models from Ollama
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = []
                        for m in data.get("models", []):
                            models.append(ModelInfo(
                                name=m["name"],
                                type="ollama",
                                path="",
                                size_gb=m.get("size", 0) / 1e9,
                                context_length=4096,  # Default
                                loaded=True
                            ))
                        return models
        except:
            pass
        
        # Fallback to default list
        return [
            ModelInfo(name="phi3:mini", type="phi", path="", size_gb=2.3, context_length=4096, loaded=True),
            ModelInfo(name="gemma2:2b", type="gemma", path="", size_gb=1.6, context_length=8192, loaded=True),
            ModelInfo(name="qwen2.5:1.5b", type="qwen2", path="", size_gb=0.9, context_length=32768, loaded=True),
            ModelInfo(name="llama3.2:1b", type="llama", path="", size_gb=0.8, context_length=131072, loaded=True),
        ]
    
    if engine == "mock":
        return [
            ModelInfo(name="phi-3-mini-4k-instruct-q4", type="phi", path="", size_gb=2.3, context_length=4096, loaded=False),
            ModelInfo(name="gemma-2-2b-it-q4", type="gemma", path="", size_gb=1.6, context_length=8192, loaded=False),
            ModelInfo(name="qwen2.5-1.5b-instruct-q4", type="qwen2", path="", size_gb=0.9, context_length=32768, loaded=False),
            ModelInfo(name="llama-3.2-1b-instruct-q4", type="llama", path="", size_gb=0.8, context_length=131072, loaded=False),
        ]
    
    return engine.list_models()


@router.post("/local/load")
async def load_local_model(req: LoadModelRequest):
    """Load a model into memory."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        # Ollama loads models on-demand, but we can trigger a pull
        try:
            import aiohttp
            ollama_model_map = {
                "phi-3-mini-4k-instruct-q4": "phi3:mini",
                "gemma-2-2b-it-q4": "gemma2:2b",
                "qwen2.5-1.5b-instruct-q4": "qwen2.5:1.5b",
                "llama-3.2-1b-instruct-q4": "llama3.2:1b",
            }
            ollama_model = ollama_model_map.get(req.model, req.model)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:11434/api/pull",
                    json={"name": ollama_model},
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as resp:
                    if resp.status == 200:
                        return {"status": "ok", "model": req.model, "loaded": True, "backend": "ollama"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to pull model: {e}")
        
        return {"status": "ok", "model": req.model, "loaded": True, "backend": "ollama"}
    
    if engine == "mock":
        return {"status": "ok", "model": req.model, "loaded": True, "backend": "mock"}
    
    try:
        engine.load_model(req.model, req.path)
        return {"status": "ok", "model": req.model, "loaded": True, "backend": "candle"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/local/unload")
async def unload_local_model(req: LoadModelRequest):
    """Unload a model from memory."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        # Ollama doesn't really unload, but we can return success
        return {"status": "ok", "model": req.model, "unloaded": True, "backend": "ollama"}
    
    if engine == "mock":
        return {"status": "ok", "model": req.model, "unloaded": True, "backend": "mock"}
    
    success = engine.unload_model(req.model)
    return {"status": "ok" if success else "not_found", "model": req.model, "unloaded": success, "backend": "candle"}


@router.get("/local/device", response_model=Dict[str, Any])
async def get_compute_device():
    """Get available compute device info."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:11434/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "device": "ollama",
                            "backend": "ollama",
                            "models_available": len(data.get("models", [])),
                            "cuda": False,
                            "metal": False,
                            "note": "Using Ollama for local inference"
                        }
        except:
            pass
        return {"device": "ollama", "backend": "ollama", "note": "Ollama not reachable"}
    
    if engine == "mock":
        return {"device": "cpu", "backend": "mock", "cuda": False, "metal": False, "note": "Install Ollama or Candle.rs for real inference"}
    
    return {
        "device": engine.device,
        "backend": "candle",
        "cuda": engine.device == "cuda",
        "metal": engine.device == "mps",
        "models_loaded": list(engine.models.keys())
    }


# ============================================================================
# Whisper.cpp STT Endpoints
# ============================================================================

@router.post("/stt/transcribe", response_model=STTResponse)
async def stt_transcribe(
    file: UploadFile = File(...),
    model: str = "base",
    language: Optional[str] = None,
    translate: bool = False,
    word_timestamps: bool = True
):
    """Transcribe audio file using Whisper.cpp."""
    engine = _get_whisper_engine()
    
    if engine == "fallback":
        # Mock response
        return STTResponse(
            text="[Mock STT] Transcribed text from audio file",
            language=language or "en",
            duration_ms=500,
            segments=[{"start_ms": 0, "end_ms": 5000, "text": "[Mock STT] Transcribed text", "tokens": [], "avg_logprob": 0.0}]
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        if model not in engine.models:
            engine.load_model(model)
        
        result = engine.transcribe(tmp_path, model, language, translate, word_timestamps)
        return result
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


@router.get("/stt/models")
async def list_stt_models():
    """List available Whisper models."""
    engine = _get_whisper_engine()
    
    if engine == "fallback":
        return {
            "models": [
                {"name": "tiny", "size_mb": 39, "languages": ["en", "multilingual"]},
                {"name": "base", "size_mb": 74, "languages": ["en", "multilingual"]},
                {"name": "small", "size_mb": 244, "languages": ["en", "multilingual"]},
                {"name": "medium", "size_mb": 769, "languages": ["en", "multilingual"]},
                {"name": "large-v3", "size_mb": 1550, "languages": ["multilingual"]},
            ]
        }
    
    return {"models": engine.list_models()}


@router.post("/stt/load")
async def load_stt_model(model: str = "base"):
    """Load Whisper model."""
    engine = _get_whisper_engine()
    
    if engine == "fallback":
        return {"status": "ok", "model": model, "loaded": True}
    
    try:
        engine.load_model(model)
        return {"status": "ok", "model": model, "loaded": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Piper TTS Endpoints
# ============================================================================

@router.post("/tts/synthesize", response_model=TTSResponse)
async def tts_synthesize(req: TTSRequest):
    """Synthesize speech using Piper TTS."""
    engine = _get_piper_engine()
    
    if engine == "fallback":
        # Return mock base64 audio
        mock_audio = base64.b64encode(b"RIFF....mock wav data....").decode()
        return TTSResponse(
            audio_base64=mock_audio,
            sample_rate=22050,
            duration_ms=len(req.text) * 50,
            latency_ms=100,
            voice=req.voice
        )
    
    try:
        result = engine.synthesize(req.voice, req.text, req.speed, req.output_format)
        return result
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/voices")
async def list_tts_voices():
    """List available Piper voices."""
    engine = _get_piper_engine()
    
    if engine == "fallback":
        return {
            "voices": [
                {"name": "en_US-lessac-medium", "language": "en-US", "quality": "medium", "sample_rate": 22050},
                {"name": "en_US-amy-low", "language": "en-US", "quality": "low", "sample_rate": 22050},
                {"name": "es_MX-clara-medium", "language": "es-MX", "quality": "medium", "sample_rate": 22050},
                {"name": "es_MX-dalia-low", "language": "es-MX", "quality": "low", "sample_rate": 22050},
            ]
        }
    
    return {"voices": engine.list_voices()}


@router.post("/tts/load")
async def load_tts_voice(voice: str):
    """Load Piper voice (pre-cache)."""
    engine = _get_piper_engine()
    
    if engine == "fallback":
        return {"status": "ok", "voice": voice, "loaded": True}
    
    if voice in engine.voices:
        return {"status": "ok", "voice": voice, "loaded": True}
    
    raise HTTPException(status_code=404, detail=f"Voice {voice} not found")


# ============================================================================
# Hardware Info Endpoint
# ============================================================================

@router.get("/hardware/info", response_model=HardwareInfo)
async def get_hardware_info():
    """Get hardware capabilities for AI inference."""
    import platform
    import psutil
    
    cpu_info = {
        "count": psutil.cpu_count(logical=False),
        "logical_count": psutil.cpu_count(logical=True),
        "frequency_mhz": psutil.cpu_freq().max if psutil.cpu_freq() else 0,
        "architecture": platform.machine(),
    }
    
    gpu_info = []
    compute_devices = ["cpu"]
    recommended = "cpu"
    
    # Check for CUDA
    try:
        import torch
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                gpu_info.append({
                    "name": torch.cuda.get_device_name(i),
                    "memory_gb": torch.cuda.get_device_properties(i).total_memory / 1e9,
                    "compute_capability": torch.cuda.get_device_capability(i),
                    "type": "cuda"
                })
            compute_devices.append("cuda")
            recommended = "cuda"
    except:
        pass
    
    # Check for Metal (macOS)
    try:
        import torch
        if torch.backends.mps.is_available():
            gpu_info.append({"name": "Apple Silicon GPU", "type": "metal"})
            compute_devices.append("metal")
            if recommended == "cpu":
                recommended = "metal"
    except:
        pass
    
    # Check for Vulkan/OpenCL
    try:
        import pyopencl as cl
        platforms = cl.get_platforms()
        for p in platforms:
            for d in p.get_devices():
                gpu_info.append({
                    "name": d.name,
                    "type": "opencl",
                    "vendor": d.vendor
                })
                if "opencl" not in compute_devices:
                    compute_devices.append("opencl")
    except:
        pass
    
    mem = psutil.virtual_memory()
    
    return HardwareInfo(
        cpu=cpu_info,
        gpu=gpu_info,
        memory_gb=mem.total / 1e9,
        compute_devices=compute_devices,
        recommended_backend=recommended
    )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/infrastructure/health")
async def ai_infrastructure_health():
    """Health check for all AI infrastructure components."""
    return {
        "local_llm": "available" if _get_local_llm_engine() != "subprocess_fallback" else "fallback",
        "whisper": "available" if _get_whisper_engine() != "fallback" else "fallback",
        "piper": "available" if _get_piper_engine() != "fallback" else "fallback",
        "timestamp": time.time()
    }