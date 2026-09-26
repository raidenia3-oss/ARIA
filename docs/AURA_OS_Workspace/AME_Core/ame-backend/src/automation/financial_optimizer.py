"""
Financial performance optimizer for AME automation.
Prioritizes platforms by recent earnings, and updates targets.json ranks.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List


class FinancialOptimizer:
    def __init__(
        self,
        targets_path: str | Path = "ame-backend/src/config/targets.json",
        earnings_path: str | Path = "ame-backend/src/automation/earnings_report.json",
    ) -> None:
        self.targets_path = Path(targets_path)
        self.earnings_path = Path(earnings_path)
        self.window_hours = 24

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            return [] if path == self.earnings_path else []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return [] if path == self.earnings_path else []

    def _save_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _compute_earnings(self, earnings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        now = datetime.now()
        cutoff = now - timedelta(hours=self.window_hours)
        stats: Dict[str, Dict[str, Any]] = {}
        for entry in earnings:
            ts = entry.get("ts")
            platform = entry.get("platform")
            amount = entry.get("amount", 0)
            if not platform:
                continue
            try:
                t = datetime.fromisoformat(ts) if ts else now
            except Exception:
                t = now
            if t < cutoff:
                continue
            bucket = stats.setdefault(
                platform,
                {
                    "earned": 0.0,
                    "count": 0,
                    "hours_worked": 0.0,
                },
            )
            bucket["earned"] += float(amount)
            bucket["count"] += 1
        return stats

    def optimize_targets(self) -> Dict[str, Any]:
        targets = self._load_json(self.targets_path)
        earnings = self._load_json(self.earnings_path)
        stats = self._compute_earnings(earnings)
        ranked = []
        for entry in targets:
            platform = entry.get("platform") or entry.get("name") or entry.get("id")
            s = stats.get(platform, {"earned": 0.0, "count": 0, "hours_worked": 0.0})
            value = (s["earned"] / self.window_hours) if self.window_hours else 0.0
            ranked.append({"platform": platform, "rank_value": value, "stats": s})

        ranked.sort(key=lambda x: x.get("rank_value", 0.0), reverse=True)
        optimized = []
        for idx, item in enumerate(ranked, start=1):
            for target in targets:
                p = target.get("platform") or target.get("name") or target.get("id")
                if p == item["platform"]:
                    opt = dict(target)
                    opt["priority_rank"] = idx
                    opt["last_earnings_per_hour"] = item.get("rank_value", 0.0)
                    optimized.append(opt)
                    break
        self._save_json(self.targets_path, optimized)
        return {
            "status": "optimized",
            "window_hours": self.window_hours,
            "order": [x["platform"] for x in ranked],
        }
