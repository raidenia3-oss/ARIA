"""Analytics collector for AURA."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal
from backend.models import AnalyticsEvent, Anomaly, MetricSnapshot


class EventType(str, Enum):
    NARRATIVE_GENERATED = "narrative_generated"
    NARRATIVE_CLICHE_DETECTED = "narrative_cliche"
    ROUTING_DECISION = "routing_decision"
    API_CALL = "api_call"
    MOBILE_EARNING = "mobile_earning"
    UPDATE_INSTALLED = "update_installed"
    UPDATE_FAILED = "update_failed"
    EXTENSION_USED = "extension_used"
    FANFIC_PUBLISHED = "fanfic_published"
    OPTIMIZATION_APPLIED = "optimization_applied"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class AnalyticsEventDTO:
    event_type: str
    timestamp: str
    module: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class _AnalyticsDB:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def _session(self):
        return self.session_factory()

    def add_analytics_event(self, event: AnalyticsEventDTO) -> None:
        db = self._session()
        try:
            row = AnalyticsEvent(
                event_type=event.event_type,
                timestamp=datetime.fromisoformat(event.timestamp).timestamp(),
                module=event.module,
                data=json.dumps(event.data, ensure_ascii=False),
                extra=json.dumps(event.metadata, ensure_ascii=False),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def get_events_since(self, since: datetime):
        db = self._session()
        try:
            return (
                db.query(AnalyticsEvent)
                .filter(AnalyticsEvent.timestamp >= since.timestamp())
                .order_by(AnalyticsEvent.timestamp.asc())
                .all()
            )
        finally:
            db.close()

    def add_anomaly(self, anomaly: Dict[str, Any]) -> None:
        db = self._session()
        try:
            row = Anomaly(
                metric=anomaly["metric"],
                current_value=anomaly["current_value"],
                expected_range=json.dumps(anomaly.get("expected_range"), ensure_ascii=False),
                severity=anomaly["severity"],
                timestamp=datetime.fromisoformat(anomaly["timestamp"]).timestamp(),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def get_anomalies(self, limit: int = 10):
        db = self._session()
        try:
            return db.query(Anomaly).order_by(Anomaly.timestamp.desc()).limit(limit).all()
        finally:
            db.close()

    def get_metrics_history(self, hours: int = 24):
        db = self._session()
        try:
            rows = (
                db.query(MetricSnapshot)
                .filter(MetricSnapshot.created_at >= (datetime.now() - timedelta(hours=hours)).timestamp())
                .order_by(MetricSnapshot.created_at.asc())
                .all()
            )
            return [json.loads(r.metrics) for r in rows]
        finally:
            db.close()

    def get_latest_metrics(self) -> Dict[str, Any]:
        db = self._session()
        try:
            row = db.query(MetricSnapshot).order_by(MetricSnapshot.created_at.desc()).first()
            if not row:
                return {}
            return json.loads(row.metrics)
        finally:
            db.close()


class AnalyticsCollector:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)
        self.event_buffer: List[AnalyticsEvent] = []
        self.buffer_size = 100
        self.session_start = datetime.now()

    async def log_event(
        self,
        event_type: EventType,
        module: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = AnalyticsEventDTO(
            event_type=event_type.value,
            timestamp=datetime.now().isoformat(),
            module=module,
            data=data,
            metadata=metadata or {},
        )
        self.event_buffer.append(event)
        if len(self.event_buffer) >= self.buffer_size:
            await self.flush_buffer()

    async def flush_buffer(self) -> None:
        if not self.event_buffer:
            return
        for event in self.event_buffer:
            self.db.add_analytics_event(event)
        self.event_buffer.clear()

    def get_session_duration(self) -> float:
        return (datetime.now() - self.session_start).total_seconds()


class MetricsCalculator:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)

    async def get_hourly_metrics(self, hours: int = 1) -> Dict[str, Any]:
        since = datetime.now() - timedelta(hours=hours)
        events = self.db.get_events_since(since)
        total = len(events)
        minutes = max(1, hours * 60)
        return {
            "total_events": total,
            "events_per_minute": total / minutes,
            "narrative_count": sum(1 for e in events if e.module == "narrative"),
            "mobile_count": sum(1 for e in events if e.module == "mobile"),
            "routing_count": sum(1 for e in events if e.module == "routing"),
            "fanfic_count": sum(1 for e in events if e.module == "fanfic"),
            "avg_response_time_ms": self._mean([getattr(e, "data", {}) or {} for e in events if e.event_type == EventType.API_CALL]),
            "error_rate_percent": self._error_rate(events),
            "earnings_total": self._total_earnings(events),
            "earnings_per_hour": self._earnings_per_hour(events, minutes),
            "narrative_quality_score": self._mean([(getattr(e, "data", {}) or {}).get("quality_score", 50) for e in events if e.event_type == EventType.NARRATIVE_GENERATED]),
            "cliche_detection_rate": self._cliche_rate(events),
        }

    async def get_daily_metrics(self) -> Dict[str, Any]:
        return await self.get_hourly_metrics(hours=24)

    async def get_weekly_metrics(self) -> Dict[str, Any]:
        return await self.get_hourly_metrics(hours=168)

    def _mean(self, values: List[Any]) -> float:
        numeric = [float(v) for v in values if isinstance(v, (int, float))]
        return sum(numeric) / len(numeric) if numeric else 0.0

    def _error_rate(self, events: List) -> float:
        if not events:
            return 0.0
        errors = sum(1 for e in events if e.event_type == EventType.ERROR_OCCURRED)
        return (errors / len(events)) * 100

    def _total_earnings(self, events: List) -> float:
        total = 0.0
        for e in events:
            if e.event_type == EventType.MOBILE_EARNING:
                total += float((getattr(e, "data", {}) or {}).get("amount", 0))
        return total

    def _earnings_per_hour(self, events: List, minutes: int) -> float:
        total = self._total_earnings(events)
        hours = minutes / 60.0
        return total / hours if hours > 0 else 0.0

    def _cliche_rate(self, events: List) -> float:
        total_narrative = sum(1 for e in events if e.event_type == EventType.NARRATIVE_GENERATED)
        cliche_events = sum(1 for e in events if e.event_type == EventType.NARRATIVE_CLICHE_DETECTED)
        if total_narrative == 0:
            return 0.0
        return (cliche_events / total_narrative) * 100


class AnomalyDetector:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)
        self.historical_baseline: Dict[str, Dict[str, float]] = {}

    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        current_metrics = await self._get_current_metrics()
        anomalies: List[Dict[str, Any]] = []
        for metric, value in current_metrics.items():
            if await self._is_anomaly(metric, value):
                anomalies.append({
                    "metric": metric,
                    "current_value": value,
                    "expected_range": self.historical_baseline.get(metric),
                    "severity": self._calc_severity(metric, value),
                    "timestamp": datetime.now().isoformat(),
                })
        for anomaly in anomalies:
            self.db.add_anomaly(anomaly)
        return anomalies

    async def _is_anomaly(self, metric: str, value: float) -> bool:
        baseline = self.historical_baseline.get(metric)
        if not baseline:
            return False
        mean = baseline.get("mean", 0)
        std = baseline.get("std", 1)
        z_score = abs((value - mean) / std) if std > 0 else 0
        return z_score > 2.0

    def _calc_severity(self, metric: str, value: float) -> str:
        if "error" in metric and value > 5.0:
            return "critical"
        if "response_time" in metric and value > 500:
            return "high"
        return "medium"

    async def _get_current_metrics(self) -> Dict[str, float]:
        return {
            "error_rate": 0.5,
            "response_time": 150.0,
            "earnings_per_hour": 4.2,
        }


class PredictiveModel:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)

    async def predict_next_hour(self) -> Dict[str, Any]:
        history = self.db.get_metrics_history(hours=24)
        if len(history) < 2:
            return {"error": "Not enough historical data"}
        return {
            "predicted_earnings": self._predict_earnings(history),
            "predicted_narrative_quality": self._predict_quality(history),
            "predicted_error_rate": self._predict_errors(history),
            "confidence": 0.75,
        }

    def _predict_earnings(self, history: List) -> float:
        if not history:
            return 0.0
        recent = [float(h.get("earnings_per_hour", 0)) for h in history[-6:]]
        trend = sum(recent) / len(recent)
        return float(trend * 1.02)

    def _predict_quality(self, history: List) -> float:
        if not history:
            return 50.0
        recent = [float(h.get("narrative_quality", 50)) for h in history[-6:]]
        return sum(recent) / len(recent)

    def _predict_errors(self, history: List) -> float:
        if not history:
            return 0.5
        recent = [float(h.get("error_rate_percent", 0)) for h in history[-6:]]
        return sum(recent) / len(recent)


class InsightGenerator:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)
        self.anomaly_detector = AnomalyDetector(session_factory)
        self.predictor = PredictiveModel(session_factory)

    async def generate_insights(self) -> List[Dict[str, Any]]:
        insights: List[Dict[str, Any]] = []
        anomalies = await self.anomaly_detector.detect_anomalies()
        for anomaly in anomalies:
            insights.append({
                "type": "anomaly",
                "title": f"Anomalía detectada: {anomaly['metric']}",
                "description": f"{anomaly['severity']} - {anomaly['current_value']}",
                "action": self._recommend_action(anomaly),
                "timestamp": anomaly["timestamp"],
            })
        predictions = await self.predictor.predict_next_hour()
        if predictions.get("predicted_earnings", 0) > 150:
            insights.append({
                "type": "opportunity",
                "title": "🚀 Earnings trend muy bueno",
                "description": f"Predicción: ${predictions['predicted_earnings']:.2f}/h",
                "action": "Aumentar recursos en Mobile Automation",
                "timestamp": datetime.now().isoformat(),
            })
        trending = await self._detect_trending_fanfic_topics()
        if trending:
            insights.append({
                "type": "trending",
                "title": "📈 Tema en tendencia detectado",
                "description": f"'{trending}' está trending",
                "action": "Generar historias de este tema",
                "timestamp": datetime.now().isoformat(),
            })
        return insights

    def _recommend_action(self, anomaly: Dict[str, Any]) -> str:
        metric = anomaly["metric"]
        if "error" in metric:
            return "Revisar logs y reintentar"
        if "response_time" in metric:
            return "Aumentar caching o recursos"
        return "Investigar manualmente"

    async def _detect_trending_fanfic_topics(self) -> Optional[str]:
        return "Supernatural Romance"


class RecommendationEngine:
    def __init__(self, session_factory) -> None:
        self.db = _AnalyticsDB(session_factory)

    async def get_recommendations(self) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []
        metrics = self.db.get_latest_metrics()
        if metrics.get("mobile_earnings_per_hour", 0) < 2.0:
            recommendations.append({
                "type": "mobile_optimization",
                "priority": "high",
                "text": "Habilitar más apps de mobile automation para aumentar ganancias",
                "expected_impact": "+$50/día",
            })
        if metrics.get("narrative_quality_score", 100) < 75:
            recommendations.append({
                "type": "narrative_improvement",
                "priority": "medium",
                "text": "Aumentar ClichéThreshold para mejor calidad",
                "expected_impact": "+5 puntos de quality",
            })
        if metrics.get("fanfic_published_daily", 0) < 5:
            recommendations.append({
                "type": "extension_usage",
                "priority": "medium",
                "text": "Promover uso de Browser Extension para publicar más historias",
                "expected_impact": "+10 historias/día",
            })
        if metrics.get("api_error_rate", 0) > 1.0:
            recommendations.append({
                "type": "routing_optimization",
                "priority": "high",
                "text": "Ajustar routing weights para menos errores",
                "expected_impact": "-50% error rate",
            })
        return recommendations
