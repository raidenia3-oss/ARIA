"""Rating system for AURA Marketplace."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Review:
    review_id: str
    app_id: str
    user_id: str
    rating: int
    comment: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    status: str = "published"


class SpamDetector:
    """Detecta reviews spam."""

    def __init__(self) -> None:
        self.spam_patterns = [
            "clic aquí",
            "gana dinero",
            "promoción",
            "descuento exclusivo",
            "regístrate ahora",
        ]

    def evaluate(self, text: str) -> Dict[str, Any]:
        lower = text.lower()
        hits = [p for p in self.spam_patterns if p in lower]
        score = max(0.0, 1.0 - len(hits) * 0.25)
        return {
            "score": round(score, 2),
            "spam": len(hits) > 0,
            "hits": hits,
        }


class RatingSystem:
    """Sistema de calificaciones y reviews."""

    def __init__(self) -> None:
        self.reviews: Dict[str, Review] = {}
        self.ratings: Dict[str, List[int]] = {}

    def add_review(self, review: Review) -> Review:
        self.reviews[review.review_id] = review
        self.ratings.setdefault(review.app_id, []).append(review.rating)
        return review

    def get_app_rating(self, app_id: str) -> Dict[str, Any]:
        values = self.ratings.get(app_id, [])
        if not values:
            return {"app_id": app_id, "average": 0.0, "count": 0, "distribution": {}}
        distribution = {str(i): 0 for i in range(1, 6)}
        for v in values:
            distribution[str(v)] = distribution.get(str(v), 0) + 1
        return {
            "app_id": app_id,
            "average": round(sum(values) / len(values), 2),
            "count": len(values),
            "distribution": distribution,
        }

    def get_reviews(self, app_id: str, limit: int = 50) -> List[Review]:
        return [r for r in self.reviews.values() if r.app_id == app_id][-limit:]

    def detect_spam(self, text: str) -> Dict[str, Any]:
        detector = SpamDetector()
        return detector.evaluate(text)
