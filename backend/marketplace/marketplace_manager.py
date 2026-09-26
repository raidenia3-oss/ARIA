# -*- coding: utf-8 -*-
"""AURA OS — Marketplace Manager.

Internal marketplace for selling AURA-generated content:
fanfics, code templates, images, datasets, music tracks.
"""
from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Marketplace")

CONTENT_CATEGORIES = ["fanfic", "code_template", "image", "dataset", "music"]
CATEGORY_LABELS = {
    "fanfic": "Fanfic",
    "code_template": "Code Templates",
    "image": "Images",
    "dataset": "Datasets",
    "music": "Music Tracks",
}
PRICE_RANGES = {
    "fanfic": (0.50, 10.00),
    "code_template": (1.00, 25.00),
    "image": (0.25, 15.00),
    "dataset": (5.00, 50.00),
    "music": (0.50, 20.00),
}


class MarketplaceManager:
    """Internal marketplace: publish, buy, royalties, recommendations."""

    def __init__(self) -> None:
        self.listings: Dict[str, Dict[str, Any]] = {}
        self.transactions: List[Dict[str, Any]] = []
        self.sales_count: int = 0
        self.total_revenue: float = 0.0

    async def list_content(self, filter_by: Optional[str] = None) -> List[Dict[str, Any]]:
        results = list(self.listings.values())

        if filter_by and filter_by in CATEGORY_LABELS:
            results = [r for r in results if r.get("category") == filter_by]

        results_sorted = sorted(results, key=lambda x: x.get("sales", 0), reverse=True)

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "price": f"${r['price']:.2f}",
                "sales": r.get("sales", 0),
                "author": r.get("author", "AURA"),
                "rating": r.get("rating", round(random.uniform(3.0, 5.0), 1)),
                "description": r.get("description", ""),
            }
            for r in results_sorted
        ]

    async def publish_content(self, content: str, price: float, category: str = "fanfic") -> Dict[str, Any]:
        if category not in CONTENT_CATEGORIES:
            raise ValueError(f"Invalid category: {category}")

        price = max(0.01, min(price, 100.0))

        content_id = str(uuid.uuid4())[:8]
        title = (content[:60].strip() if content else f"{CATEGORY_LABELS.get(category, category)} #{random.randint(100, 999)}") + "..."

        listing = {
            "id": content_id,
            "title": title,
            "content": content,
            "price": price,
            "category": category,
            "author": "AURA",
            "sales": 0,
            "rating": 0.0,
            "description": content[:200] if content else "",
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }
        self.listings[content_id] = listing

        result = {
            "content_id": content_id,
            "title": title,
            "url": f"/marketplace/{category}/{content_id}",
            "price": price,
            "category": category,
            "status": "published",
            "published_at": datetime.now().isoformat(),
        }

        logger.info("Published: %s at $%.2f", title, price)
        return result

    async def buy_content(self, content_id: str, payment: Dict[str, Any]) -> Dict[str, Any]:
        listing = self.listings.get(content_id)
        if not listing:
            raise ValueError(f"Content not found: {content_id}")
        if listing.get("status") != "active":
            raise ValueError(f"Content not available: {content_id}")

        buyer = payment.get("buyer", "anonymous")
        amount = listing["price"]

        listing["sales"] += 1
        self.sales_count += 1
        self.total_revenue += amount

        transaction = {
            "transaction_id": f"TXN-{int(datetime.now().timestamp())}",
            "content_id": content_id,
            "buyer": buyer,
            "seller": listing.get("author", "AURA"),
            "amount": amount,
            "category": listing["category"],
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        }
        self.transactions.append(transaction)

        return {
            "transaction_id": transaction["transaction_id"],
            "content_id": content_id,
            "content_title": listing["title"],
            "buyer": buyer,
            "amount": amount,
            "download_url": f"/marketplace/download/{content_id}",
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        }

    async def earn_royalties(self) -> Dict[str, Any]:
        by_category: Dict[str, float] = {}
        by_content: List[Dict[str, Any]] = []

        for listing in self.listings.values():
            cat = listing.get("category", "unknown")
            revenue = listing.get("sales", 0) * listing.get("price", 0)
            by_category[cat] = by_category.get(cat, 0) + revenue
            by_content.append({
                "id": listing["id"],
                "title": listing["title"],
                "sales": listing.get("sales", 0),
                "earnings": round(revenue, 2),
                "category": cat,
            })

        by_content.sort(key=lambda x: x["earnings"], reverse=True)

        return {
            "royalty_id": f"ROY-{int(datetime.now().timestamp())}",
            "total_earnings": round(self.total_revenue, 2),
            "total_sales": self.sales_count,
            "by_category": {k: round(v, 2) for k, v in by_category.items()},
            "top_content": by_content[:10],
            "average_sale_price": round(self.total_revenue / max(self.sales_count, 1), 4),
            "calculated_at": datetime.now().isoformat(),
        }

    async def recommend_products(self) -> Dict[str, Any]:
        active = [r for r in self.listings.values() if r.get("status") == "active"]

        recommendations = sorted(active, key=lambda x: x.get("sales", 0), reverse=True)[:5]

        trending = []
        for r in recommendations:
            trending.append({
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "price": r["price"],
                "sales": r.get("sales", 0),
                "recommendation_score": round(random.uniform(0.6, 0.99), 4),
                "reason": f"Top seller in {CATEGORY_LABELS.get(r['category'], r['category'])}",
            })

        new_releases = [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "price": r["price"],
                "is_new": True,
            }
            for r in list(active)[-3:] if active
        ]

        return {
            "recommendation_id": f"REC-{int(datetime.now().timestamp())}",
            "trending": trending,
            "new_releases": new_releases,
            "total_listings": len(active),
            "generated_at": datetime.now().isoformat(),
        }


marketplace_manager = MarketplaceManager()
