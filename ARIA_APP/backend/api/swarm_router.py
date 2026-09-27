# -*- coding: utf-8 -*-
"""ARIA OS - Multi-Agent Swarm API.

Provides endpoints for parallel task execution across specialized agents:
- CodeAnalyzer: code quality, PR analysis, refactoring
- DocsWriter: documentation generation
- Tester: test execution, coverage analysis
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.base import Agent, AgentSwarm
from agents.code_analyzer import CodeAnalyzerAgent
from agents.docs_writer import DocsWriterAgent
from agents.research import ResearchAgent
from agents.tester import TesterAgent
from skills.registry import harness

logger = logging.getLogger("ARIA.Swarm")

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ============================================================================
# Global Swarm Instance
# ============================================================================

swarm = AgentSwarm(name="ARIA-Swarm")
swarm.register_agent(CodeAnalyzerAgent())
swarm.register_agent(DocsWriterAgent())
swarm.register_agent(ResearchAgent())
swarm.register_agent(TesterAgent())


# ============================================================================
# Request Models
# ============================================================================

class SwarmTaskRequest(BaseModel):
    tasks: List[Dict[str, Any]] = Field(..., min_length=1, max_length=50)
    parallel: bool = Field(default=True, description="Execute in parallel or sequential")


class AgentTaskRequest(BaseModel):
    task: Dict[str, Any]
    agent: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/execute-parallel")
async def execute_parallel_tasks(request: SwarmTaskRequest):
    """Execute multiple tasks in parallel across swarm agents.

    Tasks are distributed round-robin unless an 'agent' key specifies a target.
    """
    try:
        if request.parallel:
            results = await asyncio.wait_for(
                swarm.execute_parallel(request.tasks),
                timeout=30,
            )
        else:
            results = await asyncio.wait_for(
                swarm.execute_sequential(request.tasks),
                timeout=60,
            )

        # NUEVO: Log with harness config
        for agent in swarm.agents:
            config = harness.get_agent_config(agent.name)
            print(f"Agent {agent.name} skills: {len(config['skills'])}")

        completed = len([r for r in results if r.get("status") == "success"])
        failed = len([r for r in results if r.get("status") == "error"])

        return {
            "status": "success",
            "results": results,
            "total_tasks": len(request.tasks),
            "completed": completed,
            "failed": failed,
            "parallel": request.parallel,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Swarm execution timed out")
    except Exception as e:
        logger.error(f"Swarm execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_single_task(request: AgentTaskRequest):
    """Execute a single task on a specific agent (or any available agent)."""
    agent = swarm.get_agent(request.agent) if request.agent else None
    if agent is None and swarm.agents:
        agent = swarm.agents[0]
    if agent is None:
        raise HTTPException(status_code=503, detail="No agents available")

    try:
        result = await agent.work(request.task)
        return result
    except Exception as e:
        logger.error(f"Agent task failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def swarm_status():
    """Return current swarm status with all agent details."""
    return swarm.status()


@router.get("/agents")
async def list_agents():
    """List all registered agents."""
    return {
        "agents": [a.to_dict() for a in swarm.agents],
        "count": len(swarm.agents),
    }


@router.get("/agents/{name}")
async def get_agent_detail(name: str):
    """Get detailed status of a specific agent."""
    agent = swarm.get_agent(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return agent.to_dict()


@router.get("/history")
async def swarm_history(limit: int = 50):
    """Get recent task execution history."""
    return {
        "history": swarm.history[-limit:],
        "total": len(swarm.history),
    }


@router.post("/agents/{name}/reset")
async def reset_agent(name: str):
    """Reset an agent's error count and status."""
    agent = swarm.get_agent(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    agent.status = "idle"
    agent.error_count = 0
    return {"status": "reset", "agent": name}


# ============================================================================
# Skill Registry (Pi Agent harness pattern)
# ============================================================================

class SkillRegistry:
    """Maps skill names to swarm agents for skill-triggered dispatch."""

    def __init__(self, swarm_instance: AgentSwarm):
        self.swarm = swarm_instance
        self._skill_map: Dict[str, str] = {}  # skill_name -> agent_name
        self._skill_prompts: Dict[str, str] = {}  # skill_name -> system prompt

    def register(self, skill_name: str, agent_name: str, prompt: str = ""):
        """Register a skill-to-agent mapping with optional prompt template."""
        if self.swarm.get_agent(agent_name) is None:
            raise ValueError(f"Agent '{agent_name}' not found in swarm")
        self._skill_map[skill_name] = agent_name
        if prompt:
            self._skill_prompts[skill_name] = prompt

    def get_agent_for_skill(self, skill_name: str) -> Optional[str]:
        return self._skill_map.get(skill_name)

    def get_prompt_for_skill(self, skill_name: str) -> str:
        return self._skill_prompts.get(skill_name, "")

    def list_skills(self) -> Dict[str, str]:
        return dict(self._skill_map)


# Global skill registry instance
skill_registry = SkillRegistry(swarm)
skill_registry.register("code-review", "CodeAnalyzer",
    "Review the following code for quality, security, and best practices. Be thorough.")
skill_registry.register("docs", "DocsWriter",
    "Generate comprehensive, well-structured documentation. Include examples.")
skill_registry.register("test", "Tester",
    "Write and execute thorough tests. Report coverage and any failures.")
skill_registry.register("research", "ResearchAgent",
    "Research social media content, videos, and web topics. Analyze importance and classify.")


@router.get("/skills")
async def list_skills():
    """List all registered skill-to-agent mappings."""
    return {
        "skills": skill_registry.list_skills(),
        "count": len(skill_registry.list_skills()),
    }


@router.post("/skills/{skill_name}/dispatch")
async def dispatch_skill_task(skill_name: str, task: Dict[str, Any]):
    """Dispatch a task to the agent mapped to a skill name (Pi Agent pattern)."""
    agent_name = skill_registry.get_agent_for_skill(skill_name)
    if agent_name is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not registered")

    agent = swarm.get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=503, detail=f"Agent '{agent_name}' not available")

    # Inject skill-specific system prompt
    skill_prompt = skill_registry.get_prompt_for_skill(skill_name)
    if skill_prompt:
        task = {**task, "system_prompt": skill_prompt}

    try:
        result = await agent.work(task)
        return result
    except Exception as e:
        logger.error(f"Skill dispatch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
async def research_task(task: Dict[str, Any]):
    """Execute a social media / video research task via ResearchAgent."""
    agent = swarm.get_agent("ResearchAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="ResearchAgent not available")
    try:
        return await agent.work(task)
    except Exception as e:
        logger.error(f"Research task failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research/batch")
async def research_batch(urls: List[str]):
    """Analyze multiple URLs in parallel via ResearchAgent."""
    agent = swarm.get_agent("ResearchAgent")
    if agent is None:
        raise HTTPException(status_code=503, detail="ResearchAgent not available")
    tasks = [{"url": u} for u in urls[:10]]
    try:
        results = await asyncio.wait_for(
            swarm.execute_parallel(tasks), timeout=120
        )
        success = len([r for r in results if r.get("status") == "success"])
        return {
            "status": "success",
            "results": results,
            "total": len(urls),
            "completed": success,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Batch research timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_swarm() -> AgentSwarm:
    """Get the global swarm instance."""
    return swarm