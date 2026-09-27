from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from skills.registry import harness, AgentSkill
from typing import Dict, List

router = APIRouter(prefix="/api/agents/harness", tags=["agents"])


class SkillRegisterRequest(BaseModel):
    name: str
    description: str
    actions: List[str]


class PromptRequest(BaseModel):
    prompt: str


class MCPRegisterRequest(BaseModel):
    name: str
    url: str


@router.post("/skills/register")
async def register_skill(req: SkillRegisterRequest):
    """Register skill (Pi Agent style)"""
    skill = AgentSkill(req.name, req.description, req.actions)
    harness.register_skill(skill)
    return {
        "status": "success",
        "skill": skill.to_dict(),
    }


@router.get("/skills")
async def list_skills():
    """List all registered skills"""
    return {
        "skills": [s.to_dict() for s in harness.skills.values()],
        "count": len(harness.skills),
    }


@router.post("/prompts/{agent_name}")
async def set_agent_prompt(agent_name: str, req: PromptRequest):
    """Set custom prompt for agent (AGENTS.md style)"""
    harness.set_prompt(agent_name, req.prompt)
    return {
        "status": "success",
        "agent": agent_name,
        "prompt": req.prompt[:100] + "..." if len(req.prompt) > 100 else req.prompt,
    }


@router.get("/config/{agent_name}")
async def get_agent_config(agent_name: str):
    """Get agent configuration (harness format)"""
    return harness.get_agent_config(agent_name)


@router.post("/mcp/register")
async def register_mcp(req: MCPRegisterRequest):
    """Register MCP server (like Pi Agent)"""
    harness.register_mcp(req.name, req.url)
    return {
        "status": "success",
        "mcp": req.name,
        "url": req.url,
    }


@router.get("/mcp/list")
async def list_mcp_servers():
    """List all MCP servers"""
    return {
        "servers": harness.mcp_servers,
        "count": len(harness.mcp_servers),
    }