"""Task planner routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.post("/plan")
async def create_plan(goal: str):
    return {"plan": [], "goal": goal, "status": "ok"}
