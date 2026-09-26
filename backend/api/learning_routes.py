# -*- coding: utf-8 -*-
"""AURA OS — Learning API Routes.

Endpoints for autonomous learning system:
- /api/learning/status
- /api/learning/cycle
- /api/learning/evaluate
- /api/learning/proposals
- /api/learning/prompts
- /api/learning/knowledge
- /api/learning/bottlenecks
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/status")
async def learning_status() -> Dict[str, Any]:
    from backend.daemon.learning_daemon import learning_daemon
    from backend.learning.mistake_memory import mistake_memory
    from backend.learning.auto_prompt import auto_prompt_generator
    from backend.learning.auto_scaling import auto_scaler
    from backend.learning.knowledge_graph import knowledge_graph
    from backend.learning.learning_loop import learning_engine
    daemon_status = learning_daemon.get_status()
    return {
        "daemon": daemon_status,
        "mistakes": mistake_memory.get_stats(),
        "prompts": auto_prompt_generator.get_stats(),
        "scaler": {
            "bottlenecks": auto_scaler.get_bottlenecks_report(),
            "perf": auto_scaler.get_perf_report(),
        },
        "kg": knowledge_graph.get_stats(),
        "evaluations": learning_engine.get_learning_report(),
    }


@router.post("/cycle")
async def run_cycle(manual: bool = False) -> Dict[str, Any]:
    from backend.daemon.learning_daemon import learning_daemon
    result = await learning_daemon.run_cycle()
    return result


@router.post("/evaluate")
async def evaluate_research(research_output: Dict[str, Any] = Body(...), source: str = "manual") -> Dict[str, Any]:
    from backend.learning.learning_loop import learning_engine
    result = learning_engine.evaluate_research(research_output, source=source)
    return {
        "evaluation_id": result.evaluation_id,
        "score": result.score,
        "metrics": result.metrics,
        "suggestions": result.suggestions,
    }


@router.get("/proposals")
async def get_proposals() -> List[Dict[str, Any]]:
    from backend.learning.learning_loop import learning_engine
    proposals = learning_engine.propose_improvements()
    return [{"proposal_id": p.proposal_id, "title": p.title, "impact": p.impact, "applied": p.applied} for p in proposals]


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal(proposal_id: str) -> Dict[str, Any]:
    from backend.learning.learning_loop import learning_engine
    applied = learning_engine.apply_proposal(proposal_id)
    return {"proposal_id": proposal_id, "applied": applied}


@router.get("/prompts")
async def get_prompts(task_type: Optional[str] = None) -> Dict[str, Any]:
    from backend.learning.auto_prompt import auto_prompt_generator
    if task_type:
        best = auto_prompt_generator.get_best_prompt(task_type)
        return {"task_type": task_type, "best_prompt": best}
    return {"stats": auto_prompt_generator.get_stats()}


@router.post("/prompts/evolve")
async def evolve_prompts(task_type: str = "research") -> Dict[str, Any]:
    from backend.learning.auto_prompt import auto_prompt_generator
    best = auto_prompt_generator.evolve(task_type)
    return {"evolved": True, "best_prompt": best.template, "fitness": best.fitness}


@router.get("/knowledge")
async def knowledge_status() -> Dict[str, Any]:
    from backend.learning.knowledge_graph import knowledge_graph
    return {
        "stats": knowledge_graph.get_stats(),
        "gaps": knowledge_graph.detect_gaps("research"),
    }


@router.get("/bottlenecks")
async def bottleneck_report() -> Dict[str, Any]:
    from backend.learning.auto_scaling import auto_scaler
    return auto_scaler.get_bottlenecks_report()


@router.get("/mistakes")
async def mistake_report(limit: int = 10) -> Dict[str, Any]:
    from backend.learning.mistake_memory import mistake_memory
    return {
        "stats": mistake_memory.get_stats(),
        "recent": mistake_memory.get_recent_mistakes(limit),
    }
