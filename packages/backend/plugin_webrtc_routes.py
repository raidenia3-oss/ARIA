"""Plugin & WebRTC routes for AURA - Module 29."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from fastapi import WebSocket

from backend.plugin_manager import PluginManager
from backend.webrtc_stream_engine import WebRTCStreamEngine

router = APIRouter(prefix="/api", tags=["webrtc", "plugin"])

webrtc_engine = WebRTCStreamEngine()
plugin_mgr = PluginManager()


# --------------------------------------------------------------------------- #
#  WebRTC Signaling                                                            #
# --------------------------------------------------------------------------- #
@router.post("/webrtc/offer")
async def webrtc_offer(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"sdp_offer": "v=0...", "client_id": "browser-1"}},
    ),
) -> Dict[str, Any]:
    sdp_offer = str(payload.get("sdp_offer", ""))
    if not sdp_offer:
        raise HTTPException(status_code=400, detail="sdp_offer is required")
    result = webrtc_engine.handle_offer(sdp_offer)
    return result


@router.post("/webrtc/ice-candidates")
async def webrtc_ice_candidates(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {"session_id": "webrtc-abc", "candidate": {"candidate": "candidate:1234", "sdp_mid": "0", "sdp_mline_index": 0}},
        },
    ),
) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    candidate = payload.get("candidate", {})
    result = webrtc_engine.handle_ice_candidate(session_id, candidate)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/webrtc/status")
async def webrtc_status(session_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    if session_id:
        session = webrtc_engine.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session_not_found")
        return {"session": session}
    return webrtc_engine.get_status()


@router.post("/webrtc/frame")
async def webrtc_process_frame(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"session_id": "webrtc-abc", "data": "base64_image_data"}},
    ),
) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    result = webrtc_engine.process_frame(session_id, payload.get("data"))
    return result


@router.post("/webrtc/audio")
async def webrtc_process_audio(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"session_id": "webrtc-abc", "data": "base64_audio_data"}},
    ),
) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    result = webrtc_engine.process_audio(session_id, payload.get("data"))
    return result


@router.websocket("/webrtc/ws/{session_id}")
async def webrtc_websocket(websocket: WebSocket, session_id: str) -> None:
    await webrtc_engine.websocket_handler(websocket, session_id=session_id)


# --------------------------------------------------------------------------- #
#  Plugin Management                                                           #
# --------------------------------------------------------------------------- #
@router.get("/plugins")
async def list_plugins(enabled_only: bool = Query(False)) -> Dict[str, Any]:
    plugins = plugin_mgr.list_plugins()
    if enabled_only:
        plugins = [p for p in plugins if p["enabled"]]
    return {"count": len(plugins), "plugins": plugins}


@router.post("/plugins")
async def register_plugin(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "manifest": {"id": "greeting", "name": "Greeting Plugin", "version": "1.0.0"},
                "code": "def plugin_execute(ctx):\n    return {'greeting': 'Hola desde AURA'}",
            }
        },
    ),
) -> Dict[str, Any]:
    manifest = payload.get("manifest")
    if not manifest or not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="manifest is required")

    filepath = payload.get("filepath")
    if filepath:
        result = plugin_mgr.load_plugin(str(filepath))
    else:
        code = payload.get("code", "")
        if not code:
            raise HTTPException(status_code=400, detail="code or filepath is required")
        result = plugin_mgr.register_plugin(manifest, str(code))

    if result.get("status") in ("error",):
        return JSONResponse(status_code=400, content=result)
    return result


@router.delete("/plugins/{plugin_id}")
async def unregister_plugin(plugin_id: str = Path(..., description="Plugin ID")) -> Dict[str, Any]:
    result = plugin_mgr.unregister_plugin(plugin_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/plugins/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str = Path(..., description="Plugin ID")) -> Dict[str, Any]:
    result = plugin_mgr.toggle_plugin(plugin_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/plugins/{plugin_id}/execute")
async def execute_plugin(
    plugin_id: str = Path(..., description="Plugin ID"),
    payload: Dict[str, Any] = Body(None, json_schema_extra={"example": {"hook_type": "plugin_execute", "context": {"user": "admin"}}}),
) -> Dict[str, Any]:
    hook_type = str((payload or {}).get("hook_type", "plugin_execute"))
    context = (payload or {}).get("context", {})
    result = plugin_mgr.execute_plugin(plugin_id, hook_type, context)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result
