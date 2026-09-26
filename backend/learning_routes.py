"""Learning & self-optimization routes for AURA - Module 25.

Endpoints REST para el aprendizaje autónomo, extracción de insights
y auto-optimización del motor.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.autonomous_learner import AutonomousLearner
from backend.self_optimization_engine import SelfOptimizationEngine

router = APIRouter(prefix="/api/learning", tags=["learning"])

learner = AutonomousLearner()
optimizer = SelfOptimizationEngine()


def _bench_simple_loop(n: int = 10000) -> int:
    total = 0
    for i in range(n):
        total += i
    return total


def _bench_list_build(n: int = 10000) -> list:
    result = []
    for i in range(n):
        result.append(i * 2)
    return result


@router.post("/crawl")
async def crawl_repo(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "repo_url": "https://github.com/kilocode-org/kilocode",
                "branch": "main",
                "module_name": "learned_kilocode",
            }
        },
    ),
) -> Dict[str, Any]:
    repo_url = str(payload.get("repo_url", ""))
    if not repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required")
    branch = str(payload.get("branch", "main"))
    module_name = payload.get("module_name") or None
    result = await asyncio.to_thread(
        learner.learn_from_repo,
        repo_url,
        branch,
        module_name,
    )
    return result


@router.get("/insights")
async def get_insights(
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    summary = learner.extractor.summary()
    insights = [
        {
            "category": i.category,
            "pattern": i.pattern,
            "description": i.description,
            "frequency": i.frequency,
        }
        for i in learner.extractor.insights[:limit]
    ]
    return {
        "count": len(insights),
        "insights": insights,
        "summary": summary,
        "scrape_summary": learner.scraper.summary(),
    }


@router.post("/synthesize")
async def synthesize(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {"module_name": "optimized_learned_module"},
        },
    ),
) -> Dict[str, Any]:
    module_name = str(payload.get("module_name", "learned_module"))
    insights = learner.extractor.insights
    if not insights:
        return {
            "status": "no_insights",
            "message": "No insights available. Run /api/learning/crawl first.",
            "generated_code_lines": 0,
        }
    code = await asyncio.to_thread(
        learner.synthesizer.synthesize_module,
        insights,
        module_name,
    )
    return {
        "status": "synthesized",
        "module_name": module_name,
        "insight_count": len(insights),
        "generated_code_lines": len(code.splitlines()),
        "source": code,
    }


@router.post("/self-optimize")
async def self_optimize(
    payload: Optional[Dict[str, Any]] = Body(
        None,
        json_schema_extra={
            "example": {"threshold_ms": 0.5, "regression_threshold": 10.0, "iterations": 5000}
        },
    ),
) -> Dict[str, Any]:
    payload = payload or {}
    threshold_ms = float(payload.get("threshold_ms", 0.5))
    regression_threshold = float(payload.get("regression_threshold", 10.0))
    iterations = int(payload.get("iterations", 5000))

    targets = [
        ("simple_loop", _bench_simple_loop, (iterations,), {}),
        ("list_build", _bench_list_build, (iterations,), {}),
    ]

    result = await asyncio.to_thread(
        optimizer.self_optimize,
        targets,
        threshold_ms,
        regression_threshold,
    )
    return result


@router.get("/self-optimize/history")
async def optimization_history(
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    history = optimizer.history(limit=limit)
    benchmark_summary = optimizer.benchmark_runner.summary()
    return {
        "count": len(history),
        "history": history,
        "benchmark_summary": benchmark_summary,
    }
