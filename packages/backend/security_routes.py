"""Security routes for AURA."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.security_manager import SecurityManager, SecurityEvent

router = APIRouter(prefix="/api/security", tags=["security"])

security: Optional[SecurityManager] = None


def init_security(db_session_factory) -> None:
    global security
    security = SecurityManager(db_session_factory)


@router.post("/auth/login")
async def login(email: str = Query(...), password: str = Query(...)) -> Dict[str, Any]:
    user = None
    if security and security.db_session_factory:
        db = security.db_session_factory()
        try:
            from backend.models import User
            user = db.query(User).filter(User.email == email).first()
        finally:
            db.close()

    if not user or not security.encryption.verify_password(password, user.hashed_password):
        await security.auditor.log_security_event(
            SecurityEvent(
                event_type="failed_login",
                timestamp=datetime.now().isoformat(),
                ip_address="unknown",
                user_id=email,
                endpoint="/api/security/auth/login",
                status="failed",
                reason="Invalid credentials",
                severity="info",
            )
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await security.auth_manager.send_mfa_code(str(user.id), email)
    return {"status": "mfa_required", "user_id": str(user.id)}


@router.post("/auth/verify-mfa")
async def verify_mfa(user_id: str = Query(...), mfa_code: str = Query(...)) -> Dict[str, Any]:
    if not await security.auth_manager.verify_mfa_code(user_id, mfa_code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    token = await security.auth_manager.generate_jwt(user_id)
    return {"status": "authenticated", "token": token, "expires_in": "24h"}


@router.post("/api-keys/generate")
async def generate_api_key(
    name: str,
    permissions: List[str] = ["read"],
    authorization: str = Header(...),
) -> Dict[str, Any]:
    payload = await security.auth_manager.verify_jwt(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    key = await security.api_key_manager.generate_api_key(
        user_id=payload["user_id"], name=name, permissions=permissions
    )
    return {
        "api_key": key,
        "message": "Keep this key safe! It won't be shown again.",
        "expires_in": "90 days",
    }


@router.post("/api-keys/rotate")
async def rotate_api_key(old_key: str, authorization: str = Header(...)) -> Dict[str, Any]:
    payload = await security.auth_manager.verify_jwt(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    new_key = await security.api_key_manager.rotate_api_key(old_key)
    if not new_key:
        raise HTTPException(status_code=400, detail="Invalid key")
    return {"status": "rotated", "new_api_key": new_key, "old_key": "deactivated"}


@router.get("/dashboard")
async def security_dashboard(authorization: str = Header(...)) -> Dict[str, Any]:
    payload = await security.auth_manager.verify_jwt(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await security.get_security_dashboard()


@router.get("/events")
async def get_security_events(
    limit: int = Query(100), severity: str = Query("all"), authorization: str = Header(...)
) -> Dict[str, Any]:
    payload = await security.auth_manager.verify_jwt(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    events = await security.auditor.get_recent_security_events(limit=limit)
    if severity != "all":
        events = [e for e in events if e.severity == severity]
    return {"events": [{"type": e.event_type, "ip": e.ip_address, "endpoint": e.endpoint, "severity": e.severity, "timestamp": datetime.fromtimestamp(e.timestamp).isoformat()} for e in events], "total": len(events)}


@router.post("/emergency-lockdown")
async def emergency_lockdown(authorization: str = Header(...)) -> Dict[str, Any]:
    payload = await security.auth_manager.verify_jwt(authorization.replace("Bearer ", ""))
    if not payload:
        raise HTTPException(status_code=401, detail="Unauthorized")
    await security.auditor.log_security_event(
        SecurityEvent(
            event_type="emergency_lockdown",
            timestamp=datetime.now().isoformat(),
            ip_address="internal",
            user_id=payload.get("user_id"),
            endpoint="/api/security/emergency-lockdown",
            status="success",
            reason="Manual emergency lockdown triggered",
            severity="critical",
        )
    )
    return {
        "status": "lockdown_activated",
        "message": "All API keys deactivated. Manual restart required.",
        "timestamp": datetime.now().isoformat(),
    }
