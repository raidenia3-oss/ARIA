# -*- coding: utf-8 -*-
"""AURA OS - Learning Agents REST Endpoints (/api/agents)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.learning_agent_fanfic import (
    learn_fanfic_writing,
    write_fanfic_with_context,
    improve_fanfic,
)
from backend.agents.learning_agent_general import GeneralLearningAgent
from backend.agents.antigravity_integration_agent import (
    open_antigravity_IDE,
    write_and_test_code,
    improve_existing_code,
)

router = APIRouter(prefix="/api/agents", tags=["learning"])


class FanficRequest(BaseModel):
    prompt: str


class ImproveRequest(BaseModel):
    text: str


class CodeTaskRequest(BaseModel):
    task: str


class ImproveFileRequest(BaseModel):
    file_path: str


@router.post("/fanfic/write", response_model=Dict[str, Any])
async def write_fanfic_endpoint(req: FanficRequest):
    """Escribe un fanfic usando el LoRA especializado."""
    try:
        text = await write_fanfic_with_context(req.prompt)
        return {
            "response": text,
            "prompt": req.prompt,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/fanfic/improve", response_model=Dict[str, Any])
async def improve_fanfic_endpoint(req: ImproveRequest):
    """Mejora un texto de fanfic existente."""
    try:
        improved = await improve_fanfic(req.text)
        return {
            "original": req.text,
            "improved": improved,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/fanfic/train", response_model=Dict[str, Any])
async def train_fanfic_lora():
    """Entrena un LoRA especializado en escritura de fanfic."""
    try:
        lora_path = await learn_fanfic_writing()
        return {
            "adapter_path": lora_path,
            "status": "trained",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/learning/status", response_model=Dict[str, Any])
async def learning_status():
    """Estado del sistema de aprendizaje."""
    return {
        "agents": ["fanfic", "general", "antigravity"],
        "status": "active",
        "jan_url": "http://localhost:1337/v1",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/learning/run", response_model=Dict[str, Any])
async def run_learning_cycle():
    """Ejecuta un ciclo completo de aprendizaje."""
    try:
        agent = GeneralLearningAgent()
        insights = await agent.learn_all()
        return {
            "insights": insights,
            "total_insights": insights.get("total_insights", 0),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/code/task", response_model=Dict[str, Any])
async def code_task_endpoint(req: CodeTaskRequest):
    """Escribe y testea codigo usando Jan + Antigravity."""
    try:
        result = await write_and_test_code(req.task)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/code/improve", response_model=Dict[str, Any])
async def code_improve_endpoint(req: ImproveFileRequest):
    """Mejora un archivo de codigo existiente."""
    try:
        result = await improve_existing_code(req.file_path)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/antigravity/open", response_model=Dict[str, Any])
async def open_antigravity(project_name: str = "aura_project"):
    """Abre Antigravity IDE con un proyecto."""
    try:
        path = await open_antigravity_IDE(project_name)
        return {
            "project_path": path,
            "status": "opened",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
