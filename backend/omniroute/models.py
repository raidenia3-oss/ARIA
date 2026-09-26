from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class OmnirouteConfig(BaseModel):
    omniroute_url: str = "http://localhost:8080"
    timeout: int = 30
    retry_attempts: int = 3
    fallback_enabled: bool = True
    enable_context_relay: bool = True


class ProviderInfo(BaseModel):
    name: str
    model: str
    status: ProviderStatus
    latency_ms: Optional[float] = None
    score: Optional[float] = None
    last_check: Optional[datetime] = None
    supports_streaming: bool = True
    input_limit: Optional[int] = None
    output_limit: Optional[int] = None


class OmnirouteResponse(BaseModel):
    provider: str
    model: str
    response: str
    usage: Optional[Dict] = None
    latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"arbitrary_types_allowed": True}
