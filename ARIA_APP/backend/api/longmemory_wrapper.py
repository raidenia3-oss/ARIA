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
from datetime import datetime
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
# Session Management (Pi Agent harness pattern)
# ============================================================================

class SessionCreateRequest(BaseModel):
    user_id: str = Field(default=LM_USER_ID)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    title: str = Field(default="New Session")


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str
    metadata: Dict[str, Any]
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int


class SessionMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# In-memory session store (fallback when LongMemory doesn't support sessions)
_session_store: Dict[str, Dict[str, Any]] = {}


def _create_session_id() -> str:
    """Generate a unique session ID."""
    import secrets
    return f"sess_{secrets.token_hex(12)}"


def _store_session(session_id: str, data: Dict[str, Any]):
    """Store session data in memory (and LongMemory if available)."""
    _session_store[session_id] = data
    # Also store in LongMemory for persistence
    try:
        _lm_request("POST", "/v1/ingest", {
            "user_id": data.get("user_id", LM_USER_ID),
            "text": f"Session: {data.get('title', 'New Session')}",
            "metadata": {
                "type": "session",
                "session_id": session_id,
                **data.get("metadata", {}),
            },
            "facet_hint": "episodic",
        })
    except Exception:
        pass  # Best-effort persistence


def _load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Load session data from memory store."""
    return _session_store.get(session_id)


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


# ============================================================================
# Session Endpoints (Pi Agent harness pattern)
# ============================================================================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionCreateRequest):
    """Create a new conversation session (Pi Agent pattern)."""
    session_id = _create_session_id()
    now = datetime.now().isoformat()
    session_data = {
        "session_id": session_id,
        "user_id": req.user_id,
        "title": req.title,
        "created_at": now,
        "metadata": req.metadata,
        "messages": [],
    }
    _store_session(session_id, session_data)
    return SessionResponse(
        session_id=session_id,
        user_id=req.user_id,
        title=req.title,
        created_at=now,
        metadata=req.metadata,
        message_count=0,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(user_id: str = ""):
    """List all sessions for a user."""
    uid = user_id or LM_USER_ID
    sessions = [
        SessionResponse(
            session_id=sid,
            user_id=data.get("user_id", uid),
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
            message_count=len(data.get("messages", [])),
        )
        for sid, data in _session_store.items()
        if data.get("user_id") == uid
    ]
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session details by ID."""
    data = _load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session_id,
        user_id=data.get("user_id", LM_USER_ID),
        title=data.get("title", "Untitled"),
        created_at=data.get("created_at", ""),
        metadata=data.get("metadata", {}),
        message_count=len(data.get("messages", [])),
    )


@router.post("/sessions/{session_id}/messages")
async def add_session_message(session_id: str, req: SessionMessageRequest):
    """Add a message to a session (Pi Agent pattern)."""
    data = _load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    message = {
        "role": req.role,
        "content": req.content,
        "timestamp": datetime.now().isoformat(),
        "metadata": req.metadata,
    }
    data.setdefault("messages", []).append(message)
    _store_session(session_id, data)
    return {"status": "success", "session_id": session_id, "message_count": len(data["messages"])}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 50):
    """Get messages from a session."""
    data = _load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = data.get("messages", [])
    return {
        "session_id": session_id,
        "messages": messages[-limit:],
        "total": len(messages),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    del _session_store[session_id]
    return {"status": "deleted", "session_id": session_id}


@router.post("/sessions/{session_id}/recall")
async def session_recall(session_id: str, req: RetrieveRequest):
    """Retrieve memories associated with a session (Pi Agent pattern)."""
    data = _load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    # Enhance query with session context
    session_context = " ".join(
        m["content"] for m in data.get("messages", [])[-5:]
    )
    enhanced_query = f"{req.query} {session_context}".strip()
    # Use the standard retrieve with enhanced query
    payload = {
        "text": enhanced_query,
        "mode": req.mode,
        "user_id": req.user_id,
        "k": req.top_k,
    }
    result = _lm_request("POST", "/v1/recall", payload)
    memories = result.get("data", {}).get("items", result.get("data", {}).get("results", []))
    return {
        "session_id": session_id,
        "status": "success",
        "results": memories,
        "total": len(memories),
    }