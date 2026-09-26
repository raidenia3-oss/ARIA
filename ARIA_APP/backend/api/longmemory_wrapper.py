# -*- coding: utf-8 -*-
"""ARIA OS - LongMemory HTTP Client Wrapper.

Integra el servidor LongMemory (CaviraOSS) vía API HTTP en puerto 7331.
https://github.com/CaviraOSS/LongMemory

Endpoints:
  POST /api/memory/longmemory/store   - Store memory via LongMemory ingest
  POST /api/memory/longmemory/retrieve - Retrieve memories via recall
  GET  /api/memory/longmemory/health  - Health check
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("ARIA.LongMemory")

router = APIRouter(prefix="/api/memory/longmemory", tags=["memory"])

# LongMemory server config
LM_HOST = os.environ.get("LONGMEMORY_HOST", "127.0.0.1")
LM_PORT = int(os.environ.get("LONGMEMORY_PORT", "7331"))
LM_BASE_URL = f"http://{LM_HOST}:{LM_PORT}"
LM_API_KEY = os.environ.get("LONGMEMORY_API_KEY", "change-me")
LM_USER_ID = os.environ.get("LONGMEMORY_USER_ID", "aria")


def _lm_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Make an authenticated request to the LongMemory HTTP API."""
    url = f"{LM_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LM_API_KEY}",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err = json.loads(err_body)
            raise HTTPException(status_code=e.code, detail=err.get("error", {}).get("message", str(e)))
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(status_code=e.code, detail=str(e))
    except urllib.error.URLError as e:
        raise HTTPException(status_code=503, detail=f"LongMemory server unavailable: {e.reason}")


def is_available() -> bool:
    """Check if LongMemory server is reachable."""
    try:
        _lm_request("GET", "/health")
        return True
    except Exception:
        return False


# ============================================================================
# Models
# ============================================================================

class StoreRequest(BaseModel):
    query: str
    response: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = Field(default=LM_USER_ID)


class StoreResponse(BaseModel):
    status: str
    memory_id: str
    latency_ms: int


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    mode: str = Field(default="associative")
    user_id: str = Field(default=LM_USER_ID)


class RetrieveResponse(BaseModel):
    status: str
    results: List[Dict[str, Any]]
    total: int
    latency_ms: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/store", response_model=StoreResponse)
async def store_memory(req: StoreRequest):
    """Store a conversation memory in LongMemory."""
    start = time.time()
    try:
        payload = {
            "user_id": req.user_id,
            "text": f"User: {req.query}\nAssistant: {req.response}",
            "metadata": req.metadata,
            "facet_hint": "episodic",
        }
        result = _lm_request("POST", "/v1/ingest", payload)
        node = result.get("data", {}).get("node", {})
        memory_id = node.get("id", "unknown")
        return StoreResponse(
            status="success",
            memory_id=memory_id,
            latency_ms=int((time.time() - start) * 1000),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LongMemory store failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_memory(req: RetrieveRequest):
    """Retrieve relevant memories from LongMemory."""
    start = time.time()
    try:
        payload = {
            "text": req.query,
            "mode": req.mode,
            "user_id": req.user_id,
            "k": req.top_k,
        }
        result = _lm_request("POST", "/v1/recall", payload)
        data = result.get("data", {})
        memories = data.get("items", data.get("results", data.get("memories", [])))
        return RetrieveResponse(
            status="success",
            results=memories,
            total=len(memories),
            latency_ms=int((time.time() - start) * 1000),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LongMemory retrieve failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def longmemory_health():
    """Check LongMemory server health."""
    try:
        result = _lm_request("GET", "/health")
        return {
            "status": "available",
            "type": "LongMemory",
            "url": LM_BASE_URL,
            "server": result.get("data", {}).get("status", {}),
        }
    except HTTPException as e:
        return {"status": "unavailable", "detail": e.detail}
    except Exception:
        return {"status": "unavailable"}


def init_longmemory():
    """Initialize LongMemory integration - log status."""
    if is_available():
        logger.info(f"LongMemory integration ready at {LM_BASE_URL}")
    else:
        logger.warning(f"LongMemory server not available at {LM_BASE_URL}")