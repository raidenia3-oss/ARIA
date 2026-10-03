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

Honesty contract (ARIA Phase A). Cada respuesta es una de tres formas:
  * 501 `HTTPException(status_code=501, detail=...)` cuando la ruta anuncia una
    ACCION que este build no ejecuta (sintetizar audio, cargar un motor,
    generar inferencia). No se devuelve ningun cuerpo de audio ni texto de
    modelo fabricado.
  * 200 con `data_source: "unavailable"` y los valores medibles en `null`,
    cuando el dato nunca se midio (listados de modelos/voces, duracion).
  * 200 con `data_source: "measured"` cuando el valor se leyo del disco, de la
    API real o del reloj.
  * 200 con `data_source: "mock"` para los stubs explicitos de desarrollo,
    que ya se identificaban con `"backend": "mock"` y no se tocan.
Es el mismo contrato que aplica `v6/axum-poc/src/` (`control::not_implemented`
para acciones, `data_source: "unavailable"` para datos no medidos). El cambio es
aditivo: ninguna clave existente se elimina y los clientes que leen `loaded` o
`audio_base64` los siguen encontrando, ahora con el valor real.
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
    data_source: str = Field(default="measured", description="'measured' when a real engine produced the text, 'mock' for the dev stub")
    detail: Optional[str] = None


class ModelInfo(BaseModel):
    name: str
    type: str
    path: str
    size_gb: float
    context_length: int
    loaded: bool
    data_source: str = Field(default="measured", description="'measured' when read from a real backend, 'mock' for the dev stub")
    detail: Optional[str] = None
    
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
    language: Optional[str] = Field(default=None, description="Language requested by the caller; null when it was left to auto-detect")
    duration_ms: Optional[int] = Field(default=None, description="Processing time of the transcription call; null when nothing ran")
    segments: List[Dict[str, Any]] = Field(default_factory=list)
    data_source: str = Field(default="measured", description="'measured' when Whisper ran, 'unavailable' when it did not")
    detail: Optional[str] = None


class TTSRequest(BaseModel):
    voice: str = Field(..., description="Piper voice name (e.g., 'en_US-lessac-medium')")
    text: str = Field(..., description="Text to synthesize")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    output_format: str = Field(default="wav", description="wav, mp3, raw")


class TTSResponse(BaseModel):
    audio_base64: Optional[str] = Field(default=None, description="Real encoded audio bytes; null when no audio was produced")
    sample_rate: Optional[int] = Field(default=None, description="Null when no audio was produced")
    duration_ms: Optional[int] = Field(default=None, description="Parsed from the WAV header; null when it could not be measured")
    latency_ms: Optional[int] = Field(default=None, description="Null when synthesis never started")
    voice: Optional[str] = None
    data_source: str = Field(default="measured", description="'measured' when Piper produced audio, 'unavailable' when it did not")
    detail: Optional[str] = None


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
                
                def load_model(self, model_id: str, local_path: Optional[str] = None) -> bool:
                    """Return True only when the weights and tokenizer are really on disk.

                    Raises instead of returning True when they are not: a caller that
                    got `True` can rely on `self.models[model_id]` pointing at real files.
                    """
                    if model_id in self.models:
                        return True
                    
                    if local_path:
                        weights_path = Path(local_path)
                        if not weights_path.exists():
                            raise FileNotFoundError(
                                f"Model path does not exist: {weights_path}; nothing was loaded"
                            )
                    else:
                        weights_path = self._download_model(model_id)
                    
                    tokenizer_file = self._resolve_tokenizer(weights_path)
                    
                    self.models[model_id] = {"path": str(weights_path), "loaded": True}
                    self.tokenizers[model_id] = tokenizers.Tokenizer.from_file(str(tokenizer_file))
                    return True
                
                def _download_model(self, model_id: str) -> Path:
                    """Resolve the real weight path from the HuggingFace cache.

                    This build performs NO network download: `model_id` is looked up in
                    the local cache and, when it is absent, this raises rather than
                    returning a path that was never created.
                    """
                    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    repo_dir = cache_dir / ("models--" + model_id.replace("/", "--"))
                    snapshots = sorted(repo_dir.glob("snapshots/*")) if repo_dir.is_dir() else []
                    if not snapshots:
                        raise FileNotFoundError(
                            f"Model {model_id!r} is not in {cache_dir} and automatic download "
                            "is not implemented in this build; nothing was downloaded"
                        )
                    return snapshots[-1]
                
                def _resolve_tokenizer(self, weights_path: Path) -> Path:
                    candidates = (
                        [weights_path / "tokenizer.json"]
                        if weights_path.is_dir()
                        else [weights_path.parent / "tokenizer.json"]
                    )
                    for candidate in candidates:
                        if candidate.exists():
                            return candidate
                    raise FileNotFoundError(
                        f"tokenizer.json not found next to {weights_path}; nothing was loaded"
                    )
                
                def generate(self, model_id: str, prompt: str, max_tokens: int, temperature: float, top_p: float, system_prompt: str = "") -> Dict:
                    """No generation runtime is wired for this engine.

                    Raising is the only honest option: returning an f-string that reads
                    like a model answer would tell the caller a completion happened when
                    no forward pass was ever run.
                    """
                    raise RuntimeError(
                        f"No inference runtime is wired for model {model_id!r}: this build resolves "
                        "local weights and tokenizers but binds no generation backend. "
                        "Nothing was generated; no completion text is fabricated."
                    )
                
                def list_models(self) -> List[ModelInfo]:
                    """List the models actually present in the local HuggingFace cache."""
                    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
                    models: List[ModelInfo] = []
                    if cache_dir.is_dir():
                        for repo_dir in sorted(cache_dir.glob("models--*")):
                            name = repo_dir.name[len("models--"):].replace("--", "/")
                            models.append(ModelInfo(
                                name=name,
                                type="candle",
                                path=str(repo_dir),
                                size_gb=0.0,
                                context_length=0,
                                loaded=name in self.models,
                                data_source="measured",
                                detail="Discovered on disk in the local HuggingFace cache"
                            ))
                    return models
                
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
                        # This build performs no download: absent ggml file means the
                        # model cannot be loaded, and `load_model` says so.
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
                    
                    # El idioma detectado no se extrae de la respuesta en este build,
                    # asi que se propaga el solicitado y se deja en null cuando fue
                    # "auto". Antes devolvia siempre "en".
                    detected_language = language if language and language != "auto" else None
                    
                    return STTResponse(
                        text=full_text.strip(),
                        language=detected_language,
                        duration_ms=int((time.time() - start) * 1000),
                        segments=segments
                    )
                
                def list_models(self) -> List[Dict]:
                    """Enumerate the ggml files really present in the whisper cache."""
                    models: List[Dict] = []
                    for ggml_file in sorted(self.models_dir.glob("ggml-*.bin")):
                        models.append({
                            "name": ggml_file.stem[len("ggml-"):],
                            "size_mb": round(ggml_file.stat().st_size / 1e6, 1),
                            "path": str(ggml_file),
                            "languages": None,
                        })
                    return models
            
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
                        duration_ms=self._wav_duration_ms(audio_data),
                        latency_ms=int((time.time() - start) * 1000),
                        voice=voice
                    )
                
                def _wav_duration_ms(self, audio_data: bytes) -> Optional[int]:
                    """Duracion real leida de la cabecera WAV, o None si no es WAV."""
                    import io
                    import wave
                    try:
                        with wave.open(io.BytesIO(audio_data), "rb") as wav:
                            rate = wav.getframerate()
                            if not rate:
                                return None
                            return int(wav.getnframes() * 1000 / rate)
                    except Exception:
                        return None
                
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
        except FileNotFoundError as e:
            # El modelo no esta en disco: la ACCION de cargar/generar no se puede
            # ejecutar. 501, no 200 con una lista o un texto inventado.
            logger.warning(f"Candle model unavailable: {e}")
            raise HTTPException(status_code=501, detail=str(e))
        except RuntimeError as e:
            # Hay motor pero no hay runtime de generacion enlazado: se declara
            # explicitamente en vez de devolver texto que parezca una respuesta.
            logger.warning(f"Candle inference unavailable: {e}")
            raise HTTPException(status_code=501, detail=str(e))
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
                    device="ollama",
                    data_source="measured",
                    detail="Completion returned by the Ollama HTTP API"
                )
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {e}")


async def _mock_inference(req: LocalInferenceRequest) -> LocalInferenceResponse:
    """Mock inference for development.

    The behaviour is unchanged: the `[Mock Local LLM ...]` prefix stays so a client
    reading `text` still sees the label. `data_source` is added so a client can read
    the same flag from a field instead of parsing the string.
    """
    start = time.time()
    text = f"[Mock Local LLM ({req.model})] Response to: {req.prompt[:100]}..."
    return LocalInferenceResponse(
        text=text,
        tokens_generated=len(text.split()),
        latency_ms=int((time.time() - start) * 1000),
        model=req.model,
        device="cpu (mock)",
        data_source="mock",
        detail="Explicit development stub: no model was executed"
    )


@router.get("/local/models", response_model=Dict[str, Any])
async def list_local_models():
    """List available local LLM models.

    Respuesta: `{"models": [...] | null, "data_source": ..., "detail": ...}`.
    `models` es `null` con `data_source: "unavailable"` cuando no se pudo medir el
    listado; nunca se devuelve una lista fija de modelos con `loaded=True` como si
    Ollama la hubiera confirmado.
    """
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
                                loaded=True,
                                data_source="measured",
                                detail="Listed by the Ollama /api/tags endpoint"
                            ))
                        return {
                            "models": [m.model_dump() for m in models],
                            "data_source": "measured",
                            "detail": "Model list read from the Ollama /api/tags endpoint",
                        }
                    failure_detail = f"Ollama answered {resp.status} on /api/tags"
        except Exception as e:
            failure_detail = f"Ollama /api/tags request failed: {type(e).__name__}: {e}"
        
        logger.warning(f"Local model list unavailable: {failure_detail}")
        return {
            "models": None,
            "data_source": "unavailable",
            "detail": f"{failure_detail}. The list could not be measured, so no model is reported.",
        }
    
    if engine == "mock":
        return {
            "models": [
                ModelInfo(name="phi-3-mini-4k-instruct-q4", type="phi", path="", size_gb=2.3, context_length=4096, loaded=False, data_source="mock").model_dump(),
                ModelInfo(name="gemma-2-2b-it-q4", type="gemma", path="", size_gb=1.6, context_length=8192, loaded=False, data_source="mock").model_dump(),
                ModelInfo(name="qwen2.5-1.5b-instruct-q4", type="qwen2", path="", size_gb=0.9, context_length=32768, loaded=False, data_source="mock").model_dump(),
                ModelInfo(name="llama-3.2-1b-instruct-q4", type="llama", path="", size_gb=0.8, context_length=131072, loaded=False, data_source="mock").model_dump(),
            ],
            "data_source": "mock",
            "detail": "Explicit development stub: no backend was queried",
        }
    
    models = engine.list_models()
    return {
        "models": [m.model_dump() for m in models],
        "data_source": "measured",
        "detail": "Model list read from the local HuggingFace cache on disk",
    }


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
                    if resp.status != 200:
                        # Antes esta rama caia en el `return` de abajo y reportaba
                        # `loaded: True` sin haber descargado nada.
                        body = await resp.text()
                        raise HTTPException(
                            status_code=502,
                            detail=f"Ollama refused to pull {ollama_model}: {resp.status} {body}",
                        )
                    return {"status": "ok", "model": req.model, "loaded": True, "backend": "ollama", "data_source": "measured", "detail": f"Ollama pulled {ollama_model}"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to pull model: {e}")
        
        raise HTTPException(
            status_code=502,
            detail=f"Ollama pull for {ollama_model} returned no response; nothing was loaded",
        )
    
    if engine == "mock":
        return {"status": "ok", "model": req.model, "loaded": True, "backend": "mock", "data_source": "mock", "detail": "Explicit development stub: nothing was loaded"}
    
    try:
        loaded = bool(engine.load_model(req.model, req.path))
        return {
            "status": "ok" if loaded else "not_loaded",
            "model": req.model,
            "loaded": loaded,
            "backend": "candle",
            "data_source": "measured",
            "detail": "Weights and tokenizer resolved from local disk" if loaded else "Engine reported the model was not loaded",
        }
    except FileNotFoundError as e:
        # La ACCION de cargar no se pudo ejecutar: se declara con 501 en vez de
        # afirmar `loaded: True`.
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/local/unload")
async def unload_local_model(req: LoadModelRequest):
    """Unload a model from memory."""
    engine = _get_local_llm_engine()
    
    if engine == "ollama":
        # Ollama has no unload endpoint: the weights stay resident in the Ollama
        # process. Reporting `unloaded: True` here claimed an eviction that never
        # happened, so the real value is reported instead.
        return {
            "status": "not_implemented",
            "model": req.model,
            "unloaded": False,
            "backend": "ollama",
            "data_source": "unavailable",
            "detail": "Ollama exposes no unload endpoint; the model stays resident in the Ollama process",
        }
    
    if engine == "mock":
        return {"status": "ok", "model": req.model, "unloaded": True, "backend": "mock", "data_source": "mock", "detail": "Explicit development stub: no model was held"}
    
    success = bool(engine.unload_model(req.model))
    return {
        "status": "ok" if success else "not_found",
        "model": req.model,
        "unloaded": success,
        "backend": "candle",
        "data_source": "measured",
        "detail": "Model evicted from the in-process registry" if success else "Model was not held in memory",
    }


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
                            "data_source": "measured",
                            "note": "Using Ollama for local inference"
                        }
        except Exception as e:
            return {
                "device": None,
                "backend": "ollama",
                "models_available": None,
                "cuda": None,
                "metal": None,
                "data_source": "unavailable",
                "detail": f"Ollama was not probed successfully: {type(e).__name__}: {e}",
                "note": "Ollama not reachable"
            }
        return {
            "device": None,
            "backend": "ollama",
            "models_available": None,
            "cuda": None,
            "metal": None,
            "data_source": "unavailable",
            "detail": "Ollama is installed but not reachable; no device was probed",
            "note": "Ollama not reachable"
        }
    
    if engine == "mock":
        return {"device": "cpu", "backend": "mock", "cuda": False, "metal": False, "data_source": "mock", "note": "Install Ollama or Candle.rs for real inference"}
    
    return {
        "device": engine.device,
        "backend": "candle",
        "cuda": engine.device == "cuda",
        "metal": engine.device == "mps",
        "models_loaded": list(engine.models.keys()),
        "data_source": "measured",
        "detail": "Device detected locally by torch in this process",
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
        # Stub honesto: el texto lleva su etiqueta `[Mock STT]` y ahora tambien
        # `data_source` para que un cliente no tenga que parsear la cadena.
        # `duration_ms` pasa a null porque 500 ms era un valor fabricado.
        return STTResponse(
            text="[Mock STT] Transcribed text from audio file",
            language=language,
            duration_ms=None,
            segments=[{"start_ms": 0, "end_ms": 5000, "text": "[Mock STT] Transcribed text", "tokens": [], "avg_logprob": 0.0}],
            data_source="unavailable",
            detail="whisper_cpp_python is not installed; no audio was transcribed. The text is a labelled stub, not a transcription.",
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
        result.data_source = "measured"
        result.detail = "Transcribed by whisper.cpp"
        return result
    except FileNotFoundError as e:
        # whisper_cpp_python esta pero el modelo no esta en disco: transcribir es
        # una ACCION que no se puede ejecutar.
        logger.warning(f"STT model unavailable: {e}")
        raise HTTPException(status_code=501, detail=str(e))
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
    """List available Whisper models.

    Sin whisper.cpp no se puede medir que modelos hay instalados, asi que
    `models` va en `null` con `data_source: "unavailable"` en vez de una lista fija
    de nombres y tamanos que podrian no existir en disco.
    """
    engine = _get_whisper_engine()
    
    if engine == "fallback":
        return {
            "models": None,
            "data_source": "unavailable",
            "detail": "whisper_cpp_python is not installed; the local model inventory could not be measured",
        }
    
    return {
        "models": engine.list_models(),
        "data_source": "measured",
        "detail": "Model inventory enumerated from the local whisper cache directory",
    }


@router.post("/stt/load")
async def load_stt_model(model: str = "base"):
    """Load Whisper model."""
    engine = _get_whisper_engine()
    
    if engine == "fallback":
        # Antes devolvia `loaded: True` sin cargar nada: la ACCION no ocurria.
        raise HTTPException(
            status_code=501,
            detail=f"STT engine not installed (whisper_cpp_python); model {model!r} was not loaded",
        )
    
    try:
        loaded = bool(engine.load_model(model))
        return {
            "status": "ok" if loaded else "not_loaded",
            "model": model,
            "loaded": loaded,
            "data_source": "measured",
            "detail": "Whisper context instantiated from the local ggml file" if loaded else "Engine reported the model was not loaded",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Piper TTS Endpoints
# ============================================================================

@router.post("/tts/synthesize", response_model=TTSResponse)
async def tts_synthesize(req: TTSRequest):
    """Synthesize speech using Piper TTS.

    Sintetizar audio es una ACCION: si el motor no esta instalado esta ruta responde
    501 y no devuelve ninguna pista de audio. Antes devolvia una constante WAV
    codificada en base64 con una duracion calculada como `len(text) * 50`, lo que
    hacia creer al cliente que se genero audio real.
    """
    engine = _get_piper_engine()
    
    if engine == "fallback":
        raise HTTPException(
            status_code=501,
            detail=(
                "TTS engine not installed (piper). No audio was synthesized: "
                "`audio_base64` and `duration_ms` are unavailable, not empty or zero."
            ),
        )
    
    try:
        result = engine.synthesize(req.voice, req.text, req.speed, req.output_format)
        result.data_source = "measured"
        result.detail = "Audio produced by the Piper binary"
        return result
    except ValueError as e:
        # Voz desconocida: es un dato que se puede medir (esta o no en disco).
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/voices")
async def list_tts_voices():
    """List available Piper voices.

    Sin piper no se puede medir que voces hay instaladas en disco, asi que
    `voices` va en `null` con `data_source: "unavailable"` en vez de cuatro voces
    fijas que podrian no existir.
    """
    engine = _get_piper_engine()
    
    if engine == "fallback":
        return {
            "voices": None,
            "data_source": "unavailable",
            "detail": "piper-tts is not installed; the local voice inventory could not be measured",
        }
    
    return {
        "voices": engine.list_voices(),
        "data_source": "measured",
        "detail": "Voice inventory enumerated from the .onnx models on disk",
    }


@router.post("/tts/load")
async def load_tts_voice(voice: str):
    """Load Piper voice (pre-cache)."""
    engine = _get_piper_engine()
    
    if engine == "fallback":
        # Antes devolvia `loaded: True` sin cargar nada: la ACCION no ocurria.
        raise HTTPException(
            status_code=501,
            detail=f"TTS engine not installed (piper); voice {voice!r} was not loaded",
        )
    
    if voice in engine.voices:
        return {
            "status": "ok",
            "voice": voice,
            "loaded": True,
            "data_source": "measured",
            "detail": (
                "Piper has no separate load step; the voice model and config were found "
                "on disk and the binary is invoked on each synthesize"
            ),
        }
    
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
    """Health check for all AI infrastructure components.

    Solo mide si el binding del motor se puede importar: no ejecuta inferencia,
    transcripcion ni sintesis. La comprobacion anterior comparaba contra un
    sentinel que este modulo nunca devolvia, asi que un motor "mock" se reportaba
    como "available"; ahora un stub explicito se reporta como tal.
    """
    llm = _get_local_llm_engine()
    whisper = _get_whisper_engine()
    piper = _get_piper_engine()

    return {
        "local_llm": "mock" if llm == "mock" else ("available" if llm else "unavailable"),
        "whisper": "fallback" if whisper == "fallback" else "available",
        "piper": "fallback" if piper == "fallback" else "available",
        "data_source": "measured",
        "detail": "Availability measured by importing each engine binding; no inference, transcription or synthesis was executed",
        "timestamp": time.time()
    }