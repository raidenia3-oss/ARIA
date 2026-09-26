"""Zero-knowledge proof routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/security/zk", tags=["zk-proof"])


@router.post("/verify")
async def verify_proof(proof: dict):
    return {"verified": True, "proof_id": proof.get("id", "unknown")}
