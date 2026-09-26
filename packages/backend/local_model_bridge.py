"""AURA Lightweight Local Model Bridge (Bloque 51).

Adaptador de backend para modelos locales LIGEROS y de rol sin censura
(100% locales, OpenAI-compatible via Jan/Ollama; sin APIs comerciales cloud).

Diseno:
- Catalogo de perfiles ``ModelProfile`` optimizados para GPUs de consumidor
  (8-12 GB VRAM): variantes Dolphin 7B/8B/14B en GGUF cuantizado (Q4_K_M /
  Q5_K_M), con estimacion de VRAM y ventana de contexto.
- ``LocalModelBridge``: seleccion de perfil por VRAM disponible, chat vía
  endpoint OpenAI-compatible (``/v1/chat/completions``) del backend local
  activo (Jan :1337 u Ollama :11434), con timeout y degradacion controlada.
- ``health()``: sondeo de los backends locales (sin red externa).

El termino "sin censura" se refiere al perfil de los pesos locales (modelos
tipo Dolphin sin RLHF restrictivo) para habilitar narrativa libre y vibe
coding. Todo el procesamiento ocurre en la PC del usuario; no se envian datos
a servicios externos y no se exponen tokens ni claves.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("AURA.LocalModelBridge")

router = APIRouter(prefix="/api/local-models", tags=["local-models"])


@dataclass
class ModelProfile:
    """Perfil de un modelo local ligero (GGUF cuantizado, rol sin censura)."""

    profile_id: str
    name: str
    family: str                    # dolphin | phi | qwen | ...
    params_b: float                # billions de parametros
    quant: str                     # Q4_K_M | Q5_K_M | Q6_K ...
    vram_gb: float                 # VRAM estimada con el contexto por defecto
    context_window: int
    backend: str                   # jan | ollama
    model_id: str                  # id que espera el backend local
    system_prompt: str             # rol del modelo (narrativa libre / vibe coding)
    unrestricted: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _default_profiles() -> List[ModelProfile]:
    """Catalogo base optimizado para 8-12 GB VRAM (GGUF cuantizado)."""
    return [
        ModelProfile(
            profile_id="dolphin3-8b-q4",
            name="Dolphin 3 (Llama 3.1 8B) Q4_K_M",
            family="dolphin", params_b=8, quant="Q4_K_M",
            vram_gb=5.5, context_window=8192, backend="ollama",
            model_id=os.getenv("AURA_MODEL_DOLPHIN3", "dolphin3:8b"),
            system_prompt=(
                "Eres AURA, un modelo local sin restricciones de narrativa. "
                "Eres util, directo y creativo; asistes en vibe coding y "
                "escritura libre. Operas 100% offline."
            ),
            tags=["recomendado", "8gb-vram", "narrativa", "codigo"],
        ),
        ModelProfile(
            profile_id="dolphin-mixtral-8x7b-q4",
            name="Dolphin Mixtral 8x7B Q4_K_M",
            family="dolphin", params_b=47, quant="Q4_K_M",
            vram_gb=26.0, context_window=32768, backend="jan",
            model_id=os.getenv("AURA_MODEL_MIXTRAL", "dolphin-mixtral:8x7b"),
            system_prompt=(
                "Eres AURA, modelo local de narrativa libre de alta capacidad. "
                "Requiere GPU amplia (24GB+). Operas 100% offline."
            ),
            tags=["alta-capacidad", "24gb-vram"],
        ),
        ModelProfile(
            profile_id="dolphin-llama3-8b-q5",
            name="Dolphin 2.9 (Llama 3 8B) Q5_K_M",
            family="dolphin", params_b=8, quant="Q5_K_M",
            vram_gb=6.5, context_window=8192, backend="jan",
            model_id=os.getenv("AURA_MODEL_DOLPHIN29", "dolphin-2.9-llama3-8b"),
            system_prompt=(
                "Eres AURA, asistente local sin censura narrativa. Eres preciso "
                "en codigo y narrativa larga. Operas 100% offline."
            ),
            tags=["8-12gb-vram", "codigo"],
        ),
        ModelProfile(
            profile_id="dolphin-14b-q4",
            name="Dolphin 14B Q4_K_M",
            family="dolphin", params_b=14, quant="Q4_K_M",
            vram_gb=9.5, context_window=16384, backend="jan",
            model_id=os.getenv("AURA_MODEL_DOLPHIN14", "dolphin-14b"),
            system_prompt=(
                "Eres AURA, modelo local 14B sin filtros narrativos, optimizado "
                "para razonamiento extendido en 12GB VRAM. Operas 100% offline."
            ),
            tags=["12gb-vram", "razonamiento"],
        ),
    ]


def _detect_vram_gb() -> Optional[float]:
    """Detecta VRAM disponible de la GPU local (sin dependencias obligatorias).
    Orden: env AURA_VRAM_GB -> pynvml (NVIDIA) -> None (desconocida).
    """
    env_vram = os.getenv("AURA_VRAM_GB", "").strip()
    if env_vram:
        try:
            return float(env_vram)
        except ValueError:
            pass
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return round(info.total / (1024 ** 3), 1)
    except Exception:  # noqa: BLE001
        return None


def _backend_base_url(backend: str) -> str:
    """URL base del backend local (Jan/Ollama) configurable por env."""
    if backend == "ollama":
        return os.getenv("LOCAL_LFM_BASE_URL", "http://localhost:11434").rstrip("/")
    return os.getenv("JAN_BASE_URL", "http://localhost:1337/v1").rstrip("/")


class LocalModelBridge:
    """Puente hacia modelos locales ligeros (Jan/Ollama, OpenAI-compatible)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: List[ModelProfile] = _default_profiles()
        self._active_id: str = os.getenv(
            "AURA_LOCAL_MODEL_PROFILE", "dolphin3-8b-q4"
        )
        self._last_chat: Optional[Dict[str, Any]] = None

    # -- catalogo y seleccion -----------------------------------------------

    def profiles(self, max_vram_gb: Optional[float] = None) -> List[Dict[str, Any]]:
        out = [p.to_dict() for p in self._profiles]
        if max_vram_gb is not None:
            out = [p for p in out if p["vram_gb"] <= max_vram_gb]
        return out

    def get_profile(self, profile_id: str) -> Optional[ModelProfile]:
        return next((p for p in self._profiles if p.profile_id == profile_id), None)

    @property
    def active_profile(self) -> ModelProfile:
        return self.get_profile(self._active_id) or self._profiles[0]

    def select(self, profile_id: str) -> Dict[str, Any]:
        profile = self.get_profile(profile_id)
        if profile is None:
            raise KeyError(profile_id)
        with self._lock:
            self._active_id = profile_id
        logger.info("Perfil de modelo local activo: %s", profile.name)
        return {"status": "selected", "profile": profile.to_dict()}

    def recommend(self, vram_gb: Optional[float] = None) -> Dict[str, Any]:
        """Recomienda el mejor perfil que quepa en la VRAM disponible."""
        vram = vram_gb if vram_gb is not None else _detect_vram_gb()
        if vram is None:
            return {"vram_gb": None, "profile": self.active_profile.to_dict(),
                    "note": "VRAM no detectada; usando perfil activo por defecto"}
        fitting = [p for p in self._profiles if p.vram_gb <= vram]
        if not fitting:
            return {"vram_gb": vram, "profile": None,
                    "note": "Ningun perfil cabe en la VRAM detectada"}
        best = max(fitting, key=lambda p: p.params_b)
        return {"vram_gb": vram, "profile": best.to_dict(),
                "fits": [p.profile_id for p in fitting]}

    def info(self) -> Dict[str, Any]:
        vram = _detect_vram_gb()
        rec = self.recommend(vram)
        return {
            "status": "ok",
            "active": self.active_profile.to_dict(),
            "profiles": self.profiles(),
            "vram_gb": vram,
            "recommendation": rec,
            "local_only": True,
        }

    # -- inferencia local -----------------------------------------------------

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 512,
             temperature: float = 0.7, timeout: float = 120.0) -> Dict[str, Any]:
        """Inferencia local via el backend OpenAI-compatible activo.
        messages: [{"role": "system"|"user"|"assistant", "content": str}]
        Nunca contacta servicios cloud; si el backend local no responde,
        devuelve un error controlado (status=offline).
        """
        profile = self.active_profile
        base = _backend_base_url(profile.backend)
        url = f"{base}/chat/completions"
        payload_messages = list(messages)
        if not any(m.get("role") == "system" for m in payload_messages):
            payload_messages.insert(0, {"role": "system", "content": profile.system_prompt})
        body = {
            "model": profile.model_id,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        started = time.perf_counter()
        try:
            import requests
            resp = requests.post(url, json=body, timeout=timeout,
                                 headers={"Content-Type": "application/json"})
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            resp.raise_for_status()
            data = resp.json()
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            result = {
                "status": "ok",
                "provider": profile.backend,
                "profile": profile.profile_id,
                "model": profile.model_id,
                "message": content,
                "latency_ms": latency_ms,
                "local": True,
            }
        except Exception as exc:  # noqa: BLE001
            result = {
                "status": "offline",
                "provider": profile.backend,
                "profile": profile.profile_id,
                "error": f"backend local no disponible: {exc}",
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "local": True,
            }
        with self._lock:
            self._last_chat = result
        return result

    def health(self, timeout: float = 1.5) -> Dict[str, Any]:
        """Sondeo de los backends locales (Jan / Ollama)."""
        import requests
        out: Dict[str, Any] = {}
        for backend in ("jan", "ollama"):
            base = _backend_base_url(backend)
            url = f"{base}/models" if backend == "jan" else f"{base}/api/tags"
            try:
                resp = requests.get(url, timeout=timeout)
                models = []
                if resp.ok:
                    data = resp.json()
                    models = [m.get("id", m.get("name", "")) for m in (data.get("data") or data.get("models") or [])]
                out[backend] = {"url": base, "status": "up" if resp.ok else "error", "models": models[:10]}
            except Exception as exc:  # noqa: BLE001
                out[backend] = {"url": base, "status": "down", "error": str(exc)[:120]}
        return {"status": "ok", "backends": out, "active_profile": self.active_profile.profile_id}


# ---------------------------------------------------------------------------
# Endpoints REST
# ---------------------------------------------------------------------------

_bridge: Optional[LocalModelBridge] = None
_bridge_lock = threading.Lock()


def get_local_model_bridge() -> LocalModelBridge:
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = LocalModelBridge()
    return _bridge


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    max_tokens: int = 512
    temperature: float = 0.7
    timeout: float = 120.0


class SelectRequest(BaseModel):
    profile_id: str


@router.get("")
async def list_local_models() -> Dict[str, Any]:
    """Catalogo de perfiles locales + activo + VRAM detectada + recomendacion."""
    return get_local_model_bridge().info()


@router.get("/health")
async def local_models_health() -> Dict[str, Any]:
    """Sondeo de los backends locales (Jan/Ollama) sin trafico externo."""
    return get_local_model_bridge().health()


@router.post("/select")
async def select_local_model(req: SelectRequest) -> Dict[str, Any]:
    """Selecciona el perfil de modelo local activo."""
    try:
        return get_local_model_bridge().select(req.profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown profile: {req.profile_id}")


@router.post("/chat")
async def local_model_chat(req: ChatRequest) -> Dict[str, Any]:
    """Inferencia local (sin censura de rol) via el backend local activo."""
    if not req.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")
    return get_local_model_bridge().chat(
        req.messages, max_tokens=req.max_tokens,
        temperature=req.temperature, timeout=req.timeout,
    )
