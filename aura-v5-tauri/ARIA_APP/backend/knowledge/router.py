"""Knowledge base query routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/query")
async def query_knowledge(q: str):
    return {"result": f"Knowledge for: {q}", "status": "ok"}
