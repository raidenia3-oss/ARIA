"""ARIA OpenAI-compatible API — allows external clients (AME mobile, Discord, Claude, etc.) to connect."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Generator, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.skills.registry import SkillRegistry


class OpenAIChatCompletionRequest(BaseModel):
    model: str = "ARIA-local"
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[str] = None


class OpenAIError(BaseModel):
    message: str
    type: str = "api_error"
    code: int = 500


router = APIRouter(prefix="/chat", tags=["openai"])


def build_openai_tools(skill_registry: SkillRegistry) -> List[Dict[str, Any]]:
    tools = []
    for item in skill_registry.list():
        name = item["full_name"].replace(".", "_")
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": item["description"] or f"Ejecuta el skill {item['name']}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "params": {
                                "type": "object",
                                "description": "Parámetros opcionales para el skill (JSON object)",
                            },
                        },
                    },
                },
            }
        )
    return tools


import time as _time


def build_openai_response(content: str, model: str = "ARIA-local") -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{int(_time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(_time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(content) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": len(content) // 2,
        },
    }


def build_openai_stream(content: str, model: str = "ARIA-local") -> Generator[str, None, None]:
    import time as _time

    chunks = content.split(" ")
    for i, chunk in enumerate(chunks):
        ts = int(_time.time())
        cid = f"chatcmplt-{int(_time.time() * 1000)}"
        if i == 0:
            payload = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": ts,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": chunk},
                        "finish_reason": None,
                    }
                ],
            }
        else:
            payload = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": ts,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": " " + chunk}, "finish_reason": None}],
            }
        yield f"data: {json.dumps(payload)}\n\n"
    cid = f"chatcmplt-{int(_time.time() * 1000)}"
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(_time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n"


def extract_last_user_message(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
    return ""


@router.post("/completions")
async def chat_completion(request: Request, req: OpenAIChatCompletionRequest):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            body = req.model_dump()
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        model = body.get("model", "ARIA-local")
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 1024)

        user_message = extract_last_user_message(messages)
        if not user_message:
            return JSONResponse(
                {"error": {"message": "No user message found", "type": "invalid_request_error"}},
                status_code=400,
            )

        from backend.app import AI_ENABLED, ai_manager, react_loop

        system_prompt = "Eres ARIA, un asistente personal avanzado. Responde en español."

        if AI_ENABLED:
            ai_result = ai_manager.chat(user_message, system_prompt=system_prompt)
            content = ai_result.get("message") or ai_result.get("response") or "Sin respuesta."
        else:
            react_result = react_loop.run(user_message, system_prompt=system_prompt)
            content = react_result.get("response", "")

        if stream:
            return StreamingResponse(
                build_openai_stream(content, model=model),
                media_type="text/event-stream",
            )

        return JSONResponse(build_openai_response(content, model=model))

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": {"message": str(e), "type": "api_error"}}, status_code=500)


@router.get("/completions")
async def chat_completion_get():
    return JSONResponse(
        {"error": {"message": "Use POST /chat/completions", "type": "invalid_request_error"}},
        status_code=405,
    )


@router.get("/tools")
async def list_tools():
    from backend.app import skill_registry

    return JSONResponse({"tools": build_openai_tools(skill_registry)})


@router.get("/models")
async def list_models():
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": "ARIA-local",
                    "object": "model",
                    "owned_by": "ARIA",
                    "permission": [],
                    "created": 0,
                },
                {
                    "id": "ARIA-ollama",
                    "object": "model",
                    "owned_by": "ARIA",
                    "permission": [],
                    "created": 0,
                },
                {
                    "id": "ARIA-gemini",
                    "object": "model",
                    "owned_by": "ARIA",
                    "permission": [],
                    "created": 0,
                },
                {
                    "id": "ARIA-groq",
                    "object": "model",
                    "owned_by": "ARIA",
                    "permission": [],
                    "created": 0,
                },
            ],
        }
    )
