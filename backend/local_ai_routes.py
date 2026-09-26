"""Local AI, Personas & Network routes for AURA - Module 27."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.character_persona_manager import DynamicPersonaEngine
from backend.local_llm_engine import OfflineLLMEngine
from backend.local_network_gateway import LocalNetworkGateway

router = APIRouter(prefix="/api", tags=["local-ai"])

llm_engine = OfflineLLMEngine()
persona_engine = DynamicPersonaEngine()
gateway = LocalNetworkGateway()
gateway.start()


# --------------------------------------------------------------------------- #
#  Local AI Models                                                             #
# --------------------------------------------------------------------------- #
@router.get("/local-ai/models")
async def list_models() -> Dict[str, Any]:
    models = await asyncio.to_thread(llm_engine.get_available_models)
    return {"count": len(models), "models": models}


@router.post("/local-ai/models")
async def pull_model(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"model_name": "llama3.2:latest"}},
    ),
) -> Dict[str, Any]:
    model_name = str(payload.get("model_name", ""))
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    result = await asyncio.to_thread(llm_engine.pull_model, model_name)
    return {"status": "pull_complete" if result.get("status_code") == 200 else "pull_failed", "detail": result}


# --------------------------------------------------------------------------- #
#  Local AI Chat                                                               #
# --------------------------------------------------------------------------- #
@router.post("/local-ai/chat")
async def local_chat(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "messages": [{"role": "user", "content": "Hola, ¿como estas?"}],
                "preferred_model": "llama3.2:latest",
                "fallbacks": ["deepseek-coder:latest"],
                "session_id": "sess_001",
            }
        },
    ),
) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")

    session_id = str(payload.get("session_id", ""))
    if session_id:
        messages = persona_engine.build_messages(
            session_id,
            messages,
            default_prompt="",
        )

    preferred = str(payload.get("preferred_model", "auto"))
    fallbacks = payload.get("fallbacks") or None
    temperature = float(payload.get("temperature", 0.7))
    max_tokens = int(payload.get("max_tokens", 2048))

    result = await llm_engine.chat(
        messages=messages,
        preferred_model=preferred,
        fallbacks=fallbacks,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return {
        "status": result.get("status", "unknown"),
        "model_used": result.get("model"),
        "tried_models": result.get("tried_models", []),
        "response": result.get("response"),
        "context_info": llm_engine.get_context_info(),
    }


# --------------------------------------------------------------------------- #
#  Character Personas                                                          #
# --------------------------------------------------------------------------- #
@router.get("/personas/cards")
async def list_personas() -> Dict[str, Any]:
    cards = persona_engine.list_cards()
    return {"count": len(cards), "cards": cards}


@router.post("/personas/cards")
async def import_persona_card(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "source": "json",
                "data": {
                    "name": "Ada Helper",
                    "description": "Asistente AI amable",
                    "personality": "Curiosa y detallada",
                    "scenario": "Conversacion casual",
                    "first_mes": "Hola! Soy tu asistente AURA.",
                },
            }
        },
    ),
) -> Dict[str, Any]:
    source = str(payload.get("source", "json"))
    data = payload.get("data", payload.get("json"))
    if data is None:
        raise HTTPException(status_code=400, detail="data is required")
    if isinstance(data, dict):
        input_data = data
    else:
        input_data = str(data)

    if source == "file":
        filepath = str(payload.get("filepath", ""))
        if not filepath:
            raise HTTPException(status_code=400, detail="filepath is required for file source")
        card = persona_engine.parser.parse_file(filepath)
        if card is None:
            return {"status": "error", "error": "unable_to_parse_file"}
        persona_engine.cards[card.card_id] = card
        return {"status": "imported", "card_id": card.card_id, "name": card.name}

    result = persona_engine.import_card(input_data, source=source)
    if result.get("status") == "imported":
        return result
    return JSONResponse(status_code=400, content=result)


@router.delete("/personas/cards/{card_id}")
async def delete_persona_card(card_id: str) -> Dict[str, Any]:
    deleted = persona_engine.delete_card(card_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="card_not_found")
    return {"status": "deleted", "card_id": card_id}


@router.post("/personas/set-active")
async def set_active_persona(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"session_id": "sess_001", "card_id": "card-abc123"}},
    ),
) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    card_id = str(payload.get("card_id", ""))
    if not session_id or not card_id:
        raise HTTPException(status_code=400, detail="session_id and card_id are required")
    result = persona_engine.set_persona(session_id, card_id)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


# --------------------------------------------------------------------------- #
#  Local Network Gateway                                                         #
# --------------------------------------------------------------------------- #
@router.post("/network/mobile-pair")
async def mobile_pair(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"device_name": "Pixel 7", "action": "generate"}},
    ),
) -> Dict[str, Any]:
    action = str(payload.get("action", "generate"))
    if action == "validate":
        token = str(payload.get("token", ""))
        return gateway.validate_pairing(token)
    if action == "pair":
        token = str(payload.get("token", ""))
        client_info = payload.get("client_info", {})
        return gateway.pair_device(token, client_info)
    device_name = str(payload.get("device_name", "mobile-device"))
    expires_in = payload.get("expires_in")
    result = gateway.get_pairing_token(device_name, expires_in)
    return {"status": "token_generated", **result}


@router.get("/network/lan-status")
async def lan_status(discover: bool = Query(False, description="Run active discovery sweep")) -> Dict[str, Any]:
    status = gateway.status()
    if discover:
        discovered = await asyncio.to_thread(gateway.discover, timeout=3.0)
        status["active_discovery"] = {"responses": len(discovered), "instances": discovered}
    return status


@router.post("/network/api-token")
async def generate_api_token(
    payload: Dict[str, Any] = Body(None, json_schema_extra={"example": {"device_name": "remote-dashboard"}}),
) -> Dict[str, Any]:
    device_name = str((payload or {}).get("device_name", "remote-client"))
    result = gateway.generate_api_token(device_name)
    return {"status": "token_generated", **result}

