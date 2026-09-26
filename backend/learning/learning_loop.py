# -*- coding: utf-8 -*-
"""AURA OS — Learning Engine (Evaluation & Improvement Loop).

Evaluates research quality, tracks metrics, proposes improvements,
and feeds results back into the knowledge graph.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.LearningEngine")


@dataclass
class EvaluationResult:
    evaluation_id: str
    source: str
    score: float
    metrics: Dict[str, float]
    suggestions: List[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ImprovementProposal:
    proposal_id: str
    title: str
    description: str
    impact: float
    effort: str
    applied: bool = False
    timestamp: float = field(default_factory=time.time)


class LearningEngine:
    """Evaluates AURA's outputs and proposes improvements."""

    def __init__(self, history_days: int = 30) -> None:
        self.history_days = history_days
        self.evaluations: List[EvaluationResult] = []
        self.proposals: List[ImprovementProposal] = []
        self._metrics_cache: Dict[str, Any] = {}
        self._data_file = Path("data/learning/evaluations.json")
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

    def evaluate_research(self, research_output: Dict[str, Any], source: str = "deep_research") -> EvaluationResult:
        score = self._compute_research_score(research_output)
        metrics = self._extract_metrics(research_output)
        suggestions = self._generate_suggestions(research_output, score)
        eid = f"EVA-{int(time.time())}"
        result = EvaluationResult(
            evaluation_id=eid,
            source=source,
            score=score,
            metrics=metrics,
            suggestions=suggestions,
        )
        self.evaluations.append(result)
        self._save_evaluation(result)
        logger.info("Research evaluated: score=%.3f, source=%s", score, source)
        return result

    def _compute_research_score(self, output: Dict[str, Any]) -> float:
        score = 0.5
        if "papers" in output:
            score += min(len(output["papers"]) / 25, 0.15)
        if "findings" in output:
            score += min(len(output["findings"]) / 20, 0.15)
        if "summary" in output and len(str(output["summary"])) > 100:
            score += 0.05
        if "concepts" in output:
            score += min(len(output["concepts"]) / 12, 0.10)
        if "sources" in output:
            score += min(len(output["sources"]) / 10, 0.10)
        if "coverage" in output:
            coverage = output["coverage"]
            if isinstance(coverage, (int, float)):
                score += min(coverage * 0.2, 0.20)
        if "confidence" in output:
            confidence = output["confidence"]
            if isinstance(confidence, (int, float)):
                score += min(confidence * 0.15, 0.15)
        return round(min(score, 1.0), 4)

    def _extract_metrics(self, output: Dict[str, Any]) -> Dict[str, float]:
        return {
            "breadth": len(output.get("papers", output.get("findings", output.get("sources", [])))) / 25,
            "depth": output.get("coverage", 0.5) if isinstance(output.get("coverage"), (int, float)) else 0.5,
            "confidence": output.get("confidence", 0.5) if isinstance(output.get("confidence"), (int, float)) else 0.5,
            "completeness": len(str(output.get("summary", ""))) / 1000,
            "recency": self._compute_recency(output),
        }

    def _compute_recency(self, output: Dict[str, Any]) -> float:
        now = datetime.now()
        timestamps = []
        for source_list in [output.get("sources", [])]:
            if isinstance(source_list, list):
                for src in source_list:
                    if isinstance(src, dict):
                        ts = src.get("indexed_at") or src.get("created_at")
                        if ts:
                            try:
                                timestamps.append(float(ts))
                            except (ValueError, TypeError):
                                pass
        if not timestamps:
            return 0.5
        avg = sum(timestamps) / len(timestamps)
        age_days = (now.timestamp() - avg) / 86400
        return round(max(0, 1 - age_days / 365), 4)

    def _generate_suggestions(self, output: Dict[str, Any], score: float) -> List[str]:
        suggestions: List[str] = []
        if score < 0.6:
            suggestions.append("Increase source diversity for better coverage")
        if "coverage" in output and isinstance(output.get("coverage"), (int, float)) and output["coverage"] < 0.6:
            suggestions.append("Research coverage below 60% — derive deeper sub-questions")
        if "confidence" in output and isinstance(output.get("confidence"), (int, float)) and output["confidence"] < 0.7:
            suggestions.append("Low confidence — cross-validate with additional sources")
        if len(output.get("papers", [])) < 5:
            suggestions.append("Expand academic search — fewer than 5 papers found")
        if len(output.get("sources", [])) < 5:
            suggestions.append("Add more web sources to broaden perspective")
        if "findings" in output and len(output["findings"]) < 3:
            suggestions.append("Low finding count — refine extraction keywords")
        if not suggestions:
            suggestions.append("Quality acceptable — maintain current strategy")
        return suggestions

    def evaluate_automation(self, automation_name: str, result: Dict[str, Any]) -> EvaluationResult:
        success = result.get("success", False)
        score = 1.0 if success else 0.0
        score += min(len(result.get("actions", [])) / 10, 0.3)
        score = round(min(score, 1.0), 4)
        eid = f"EVA-{int(time.time())}"
        eval_result = EvaluationResult(
            evaluation_id=eid,
            source=f"automation:{automation_name}",
            score=score,
            metrics={"success": float(success), "actions": len(result.get("actions", []))},
            suggestions=[] if success else ["Investigate automation failure"],
        )
        self.evaluations.append(eval_result)
        return eval_result

    def propose_improvements(self) -> List[ImprovementProposal]:
        recent = self.evaluations[-20:] if len(self.evaluations) > 20 else self.evaluations
        if not recent:
            return []
        avg_score = sum(e.score for e in recent) / len(recent)
        proposals: List[ImprovementProposal] = []
        pid = 0
        if avg_score < 0.7:
            pid += 1
            proposals.append(ImprovementProposal(
                proposal_id=f"PROP-{pid}",
                title="Improve research quality",
                description=f"Average research score is {avg_score:.3f}. Increase source diversity and add cross-validation.",
                impact=0.3,
                effort="medium",
            ))
        low_conf = [e for e in recent if "confidence" in e.metrics and e.metrics["confidence"] < 0.6]
        if low_conf:
            pid += 1
            proposals.append(ImprovementProposal(
                proposal_id=f"PROP-{pid}",
                title="Boost confidence scores",
                description=f"{len(low_conf)} evaluations with low confidence. Add multi-source validation.",
                impact=0.2,
                effort="low",
            ))
        if len(recent) > 5:
            old = [e for e in recent if time.time() - e.timestamp > 86400]
            if len(old) > len(recent) / 2:
                pid += 1
                proposals.append(ImprovementProposal(
                    proposal_id=f"PROP-{pid}",
                    title="Increase evaluation frequency",
                    description="Most evaluations are >24h old. Run more frequent checks.",
                    impact=0.15,
                    effort="low",
                ))
        self.proposals.extend(proposals)
        return proposals

    def apply_proposal(self, proposal_id: str) -> bool:
        for p in self.proposals:
            if p.proposal_id == proposal_id and not p.applied:
                p.applied = True
                logger.info("Applied proposal: %s", p.title)
                return True
        return False

    def get_learning_report(self) -> Dict[str, Any]:
        recent = self.evaluations[-50:] if len(self.evaluations) > 50 else self.evaluations
        scores = [e.score for e in recent]
        avg = sum(scores) / len(scores) if scores else 0.0
        applied = sum(1 for p in self.proposals if p.applied)
        return {
            "total_evaluations": len(self.evaluations),
            "recent_evaluations": len(recent),
            "average_score": round(avg, 4),
            "min_score": round(min(scores), 4) if scores else 0.0,
            "max_score": round(max(scores), 4) if scores else 0.0,
            "total_proposals": len(self.proposals),
            "applied_proposals": applied,
            "pending_proposals": len(self.proposals) - applied,
            "last_evaluation": recent[-1].timestamp if recent else None,
            "score_trend": "improving" if len(scores) > 2 and scores[-1] > scores[0] else "stable",
        }

    def _save_evaluation(self, eval_result: EvaluationResult) -> None:
        try:
            if self._data_file.exists():
                data = json.loads(self._data_file.read_text())
            else:
                data = []
            data.append({
                "evaluation_id": eval_result.evaluation_id,
                "source": eval_result.source,
                "score": eval_result.score,
                "metrics": eval_result.metrics,
                "suggestions": eval_result.suggestions,
                "timestamp": eval_result.timestamp,
            })
            self._data_file.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.debug("Save evaluation failed: %s", exc)

    def _load_history(self) -> None:
        try:
            if self._data_file.exists():
                data = json.loads(self._data_file.read_text())
                for entry in data[-50:]:
                    self.evaluations.append(EvaluationResult(
                        evaluation_id=entry.get("evaluation_id", ""),
                        source=entry.get("source", ""),
                        score=entry.get("score", 0.0),
                        metrics=entry.get("metrics", {}),
                        suggestions=entry.get("suggestions", []),
                        timestamp=entry.get("timestamp", time.time()),
                    ))
        except Exception:
            pass


learning_engine = LearningEngine()
