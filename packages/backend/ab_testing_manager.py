"""A/B testing manager for AURA."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal
from backend.models import ABTest as ABTestModel


class ABTestingManager:
    def __init__(self, db_session_factory) -> None:
        self.db_session_factory = db_session_factory
        self.active_tests: Dict[str, Any] = {}

    async def create_ab_test(
        self,
        model_a: str,
        model_b: str,
        metric: str = "engagement",
        sample_size: int = 1000,
    ) -> str:
        test_id = f"abtest-{datetime.now().timestamp()}"
        test = {
            "test_id": test_id,
            "model_a": model_a,
            "model_b": model_b,
            "metric": metric,
            "start_date": datetime.now().isoformat(),
            "end_date": None,
            "sample_size": sample_size,
            "traffic_split": 0.5,
            "results_a": {},
            "results_b": {},
            "winner": None,
            "confidence": 0.0,
            "status": "running",
        }
        self.active_tests[test_id] = test
        await self._persist_test(test)
        print(f"A/B test created: {test_id}")
        return test_id

    async def record_test_result(
        self,
        test_id: str,
        model_id: str,
        engagement_score: float,
        coherence_score: float,
    ) -> None:
        test = self.active_tests.get(test_id)
        if not test:
            return
        bucket = test["results_a"] if model_id == test["model_a"] else test["results_b"]
        bucket["engagement"] = bucket.get("engagement", 0.0) + engagement_score
        bucket["coherence"] = bucket.get("coherence", 0.0) + coherence_score
        bucket["count"] = bucket.get("count", 0) + 1
        total = test["results_a"].get("count", 0) + test["results_b"].get("count", 0)
        if total >= test["sample_size"]:
            await self._finalize_test(test)

    async def _finalize_test(self, test: Dict[str, Any]) -> None:
        total_a = test["results_a"].get("count", 0)
        total_b = test["results_b"].get("count", 0)
        avg_a = test["results_a"].get("engagement", 0.0) / max(total_a, 1)
        avg_b = test["results_b"].get("engagement", 0.0) / max(total_b, 1)
        if avg_a > avg_b:
            test["winner"] = test["model_a"]
            test["confidence"] = min(100.0, ((avg_a - avg_b) / avg_b) * 100 if avg_b > 0 else 100.0)
        else:
            test["winner"] = test["model_b"]
            test["confidence"] = min(100.0, ((avg_b - avg_a) / avg_a) * 100 if avg_a > 0 else 100.0)
        test["status"] = "completed"
        test["end_date"] = datetime.now().isoformat()
        await self._persist_test(test)
        print(f"A/B test completed: {test['test_id']} winner={test['winner']}")

    async def get_test_status(self, test_id: str) -> Dict[str, Any]:
        test = self.active_tests.get(test_id)
        if not test:
            return {}
        total_a = test["results_a"].get("count", 0)
        total_b = test["results_b"].get("count", 0)
        return {
            "test_id": test_id,
            "status": test["status"],
            "model_a": test["model_a"],
            "model_b": test["model_b"],
            "progress": f"{total_a + total_b}/{test['sample_size']}",
            "avg_score_a": test["results_a"].get("engagement", 0.0) / max(total_a, 1),
            "avg_score_b": test["results_b"].get("engagement", 0.0) / max(total_b, 1),
            "winner": test["winner"],
            "confidence": test["confidence"],
        }

    async def _persist_test(self, test: Dict[str, Any]) -> None:
        db = self.db_session_factory()
        try:
            row = db.query(ABTestModel).filter(ABTestModel.test_id == test["test_id"]).first()
            if not row:
                row = ABTestModel(test_id=test["test_id"])
                db.add(row)
            row.model_a = test["model_a"]
            row.model_b = test["model_b"]
            row.metric = test["metric"]
            row.start_date = datetime.fromisoformat(test["start_date"]).timestamp()
            row.end_date = datetime.fromisoformat(test["end_date"]).timestamp() if test.get("end_date") else None
            row.sample_size = test["sample_size"]
            row.traffic_split = test["traffic_split"]
            row.results_a = json.dumps(test["results_a"], ensure_ascii=False)
            row.results_b = json.dumps(test["results_b"], ensure_ascii=False)
            row.winner = test["winner"]
            row.confidence = test["confidence"]
            row.status = test["status"]
            db.commit()
        finally:
            db.close()
