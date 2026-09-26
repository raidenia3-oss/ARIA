"""Marketplace routes for AURA API Marketplace & Distribution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.marketplace_manager import AppRegistration, AppStatus, VersionRecord, VersionStatus, MarketplaceManager
from backend.marketplace_monetization import MarketplaceMonetization
from backend.rating_system import RatingSystem, Review

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])
marketplace = MarketplaceManager()
monetization = MarketplaceMonetization()
ratings = RatingSystem()


@router.get("/health")
async def marketplace_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "apps_count": len(marketplace.registry.apps),
        "versions_count": len(marketplace.registry.versions),
        "service": "marketplace",
    }


@router.post("/apps")
async def create_app(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["app_id", "name", "description", "category", "developer"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return JSONResponse(status_code=400, content={"detail": f"Missing fields: {', '.join(missing)}"})

    app = marketplace.create_app(AppRegistration(
        app_id=str(payload["app_id"]),
        name=str(payload["name"]),
        description=str(payload["description"]),
        category=str(payload["category"]),
        developer=str(payload["developer"]),
        tags=payload.get("tags", []),
        status=payload.get("status", "draft"),
    ))
    return app.__dict__


@router.get("/apps")
async def list_apps(query: str = "", category: str = "", tags: Optional[str] = None) -> Dict[str, Any]:
    tag_list = tags.split(",") if tags else None
    apps = marketplace.search_apps(query=query, category=category, tags=tag_list)
    return {"count": len(apps), "apps": [a.__dict__ for a in apps]}


@router.get("/apps/{app_id}")
async def get_app(app_id: str) -> Dict[str, Any]:
    app = marketplace.get_app(app_id)
    if not app:
        return JSONResponse(status_code=404, content={"detail": "App not found"})
    return app.__dict__


@router.post("/apps/{app_id}/versions")
async def publish_version(app_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    app = marketplace.get_app(app_id)
    if not app:
        return JSONResponse(status_code=404, content={"detail": "App not found"})

    version = marketplace.publish_version(VersionRecord(
        version_id=f"{app_id}-{payload.get('version', '1.0.0')}",
        app_id=app_id,
        version=str(payload.get("version", "1.0.0")),
        changelog=str(payload.get("changelog", "")),
        status=payload.get("status", "beta"),
        metadata=payload.get("metadata", {}),
    ))
    return version.__dict__


@router.get("/apps/{app_id}/versions")
async def list_versions(app_id: str) -> Dict[str, Any]:
    versions = marketplace.get_versions(app_id)
    return {"app_id": app_id, "count": len(versions), "versions": [v.__dict__ for v in versions]}


@router.post("/apps/{app_id}/reviews")
async def add_review(app_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["review_id", "user_id", "rating", "comment"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return JSONResponse(status_code=400, content={"detail": f"Missing fields: {', '.join(missing)}"})

    review = ratings.add_review(Review(
        review_id=str(payload["review_id"]),
        app_id=app_id,
        user_id=str(payload["user_id"]),
        rating=int(payload["rating"]),
        comment=str(payload["comment"]),
    ))
    return review.__dict__


@router.get("/apps/{app_id}/reviews")
async def get_reviews(app_id: str, limit: int = 50) -> Dict[str, Any]:
    reviews = ratings.get_reviews(app_id, limit=limit)
    return {"app_id": app_id, "count": len(reviews), "reviews": [r.__dict__ for r in reviews]}


@router.get("/apps/{app_id}/rating")
async def get_app_rating(app_id: str) -> Dict[str, Any]:
    return ratings.get_app_rating(app_id)


@router.post("/sales")
async def record_sale(payload: Dict[str, Any]) -> Dict[str, Any]:
    required = ["app_id", "developer_id", "amount"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return JSONResponse(status_code=400, content={"detail": f"Missing fields: {', '.join(missing)}"})

    tx = monetization.record_sale(
        app_id=str(payload["app_id"]),
        developer_id=str(payload["developer_id"]),
        amount=float(payload["amount"]),
        metadata=payload.get("metadata"),
    )
    return tx.__dict__


@router.get("/developers/{developer_id}/payout")
async def developer_payout(developer_id: str) -> Dict[str, Any]:
    return monetization.payout_status(developer_id)


@router.get("/developers/{developer_id}/transactions")
async def developer_transactions(developer_id: str, limit: int = 50) -> Dict[str, Any]:
    return monetization.transaction_history(developer_id, limit=limit)


@router.post("/security/scan")
async def security_scan(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = payload.get("metadata", {})
    return marketplace.verify_security(metadata)


@router.get("/search")
async def marketplace_search(query: str = "", category: str = "", tags: Optional[str] = None) -> Dict[str, Any]:
    tag_list = tags.split(",") if tags else None
    apps = marketplace.search_apps(query=query, category=category, tags=tag_list)
    return {"count": len(apps), "apps": [a.__dict__ for a in apps]}
