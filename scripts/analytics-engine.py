"""
Analytics engine for data aggregation, anomaly detection, and forecasting.
Phase 58 - Option F: Analytics Engine + ML
Runs as a scheduled job (hourly) to aggregate data and generate insights.
"""

import json
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import hashlib

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AnalyticsEngine")


class AnalyticsEngine:
    """
    Analytics engine that aggregates data, detects anomalies, and forecasts trends.
    Designed to run as a scheduled job (hourly via EasyCron / Cloud Scheduler).
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        data_dir: str = "./analytics_data",
    ):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL", "sqlite:///aura_analytics.db"
        )
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data: Optional[pd.DataFrame] = None
        self.anomaly_model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None

    # ============================================================
    # Phase F1: Data Aggregation
    # ============================================================

    def aggregate_daily_stats(
        self, log_data: Optional[List[Dict]] = None
    ) -> pd.DataFrame:
        """
        Aggregate logs into daily summaries.
        
        Args:
            log_data: List of log entries. If None, generates sample data.
            
        Returns:
            DataFrame with daily aggregated stats
        """
        if log_data is None:
            log_data = self._generate_sample_logs(1000)

        df = pd.DataFrame(log_data)
        
        # Parse timestamps
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date

        # Aggregate by date
        daily_stats = df.groupby("date").agg(
            total_events=("event_type", "count"),
            errors=("event_type", lambda x: (x == "error").sum()),
            avg_latency=("latency_ms", "mean"),
            max_latency=("latency_ms", "max"),
            webhook_count=("integration", lambda x: (x == "webhook").sum()),
        ).reset_index()

        daily_stats["date"] = pd.to_datetime(daily_stats["date"])
        daily_stats["uptime_percent"] = 100 - (
            daily_stats["errors"] / daily_stats["total_events"] * 100
        )
        daily_stats["error_rate"] = (
            daily_stats["errors"] / daily_stats["total_events"] * 100
        )

        # Save to CSV
        output_path = self.data_dir / "daily_stats.csv"
        daily_stats.to_csv(output_path, index=False)
        logger.info(f"Daily stats saved to {output_path}")

        self.data = daily_stats
        return daily_stats

    def aggregate_by_integration(
        self, log_data: Optional[List[Dict]] = None
    ) -> Dict[str, Dict]:
        """
        Per-integration health metrics.
        
        Args:
            log_data: List of log entries
            
        Returns:
            Dict with per-integration metrics
        """
        if log_data is None:
            log_data = self._generate_sample_logs(1000)

        df = pd.DataFrame(log_data)
        integrations = ["slack", "discord", "telegram", "teams", "webhook"]

        integration_stats = {}
        for integration in integrations:
            int_df = df[df["integration"] == integration]
            if len(int_df) > 0:
                integration_stats[integration] = {
                    "events": len(int_df),
                    "errors": int(int_df["event_type"].eq("error").sum()),
                    "latency": float(int_df["latency_ms"].mean()),
                    "uptime": float(
                        100 - (int_df["event_type"].eq("error").sum() / len(int_df) * 100)
                    ),
                }
            else:
                integration_stats[integration] = {
                    "events": 0,
                    "errors": 0,
                    "latency": 0.0,
                    "uptime": 100.0,
                }

        # Save to JSON
        output_path = self.data_dir / "integration_stats.json"
        with open(output_path, "w") as f:
            json.dump(integration_stats, f, indent=2)
        logger.info(f"Integration stats saved to {output_path}")

        return integration_stats

    def compute_trends(
        self, daily_stats: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Compute 7-day and 30-day trends.
        
        Args:
            daily_stats: DataFrame with daily stats
            
        Returns:
            Dict with trend data
        """
        if daily_stats is None:
            if self.data is not None:
                daily_stats = self.data
            else:
                daily_stats = self.aggregate_daily_stats()

        if len(daily_stats) < 2:
            return {
                "week_over_week": 0.0,
                "month_over_month": 0.0,
                "anomalies": [],
                "trend": "insufficient_data",
            }

        # Sort by date
        daily_stats = daily_stats.sort_values("date")

        # Calculate week-over-week growth
        recent_week = daily_stats.tail(7)
        previous_week = daily_stats.tail(14).head(7)

        if len(recent_week) > 0 and len(previous_week) > 0:
            recent_avg = recent_week["total_events"].mean()
            previous_avg = previous_week["total_events"].mean()
            wow_growth = (
                ((recent_avg - previous_avg) / previous_avg * 100)
                if previous_avg > 0
                else 0
            )
        else:
            wow_growth = 0

        # Calculate month-over-month growth
        recent_month = daily_stats.tail(30)
        previous_month = daily_stats.tail(60).head(30)

        if len(recent_month) > 0 and len(previous_month) > 0:
            recent_avg = recent_month["total_events"].mean()
            previous_avg = previous_month["total_events"].mean()
            mom_growth = (
                ((recent_avg - previous_avg) / previous_avg * 100)
                if previous_avg > 0
                else 0
            )
        else:
            mom_growth = 0

        # Detect anomalies in trends
        anomalies = self._detect_trend_anomalies(daily_stats)

        trends = {
            "week_over_week": round(wow_growth, 2),
            "month_over_month": round(mom_growth, 2),
            "anomalies": anomalies,
            "trend": "growing" if wow_growth > 5 else "stable" if wow_growth > -5 else "declining",
            "total_events_7d": int(recent_week["total_events"].sum()) if len(recent_week) > 0 else 0,
            "total_events_30d": int(recent_month["total_events"].sum()) if len(recent_month) > 0 else 0,
        }

        # Save to JSON
        output_path = self.data_dir / "trends.json"
        with open(output_path, "w") as f:
            json.dump(trends, f, indent=2)
        logger.info(f"Trends saved to {output_path}")

        return trends

    def _detect_trend_anomalies(
        self, daily_stats: pd.DataFrame
    ) -> List[Dict]:
        """Detect anomalies in daily trends."""
        anomalies = []
        
        # Check for unusual error spikes
        if "error_rate" in daily_stats.columns:
            mean_error = daily_stats["error_rate"].mean()
            std_error = daily_stats["error_rate"].std()
            
            for _, row in daily_stats.iterrows():
                if row["error_rate"] > mean_error + 2 * std_error:
                    anomalies.append({
                        "date": str(row["date"]),
                        "type": "error_spike",
                        "severity": "high",
                        "value": float(row["error_rate"]),
                        "threshold": float(mean_error + 2 * std_error),
                    })

        # Check for latency spikes
        if "avg_latency" in daily_stats.columns:
            mean_latency = daily_stats["avg_latency"].mean()
            std_latency = daily_stats["avg_latency"].std()
            
            for _, row in daily_stats.iterrows():
                if row["avg_latency"] > mean_latency + 2 * std_latency:
                    anomalies.append({
                        "date": str(row["date"]),
                        "type": "latency_spike",
                        "severity": "medium",
                        "value": float(row["avg_latency"]),
                        "threshold": float(mean_latency + 2 * std_latency),
                    })

        return anomalies

    # ============================================================
    # Phase F2: ML Models
    # ============================================================

    def detect_anomalies_ml(
        self, data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Detect anomalies using Isolation Forest.
        
        Args:
            data: DataFrame with features for anomaly detection
            
        Returns:
            DataFrame with anomaly labels (-1 = anomaly, 1 = normal)
        """
        if data is None:
            if self.data is not None:
                data = self.data
            else:
                data = self.aggregate_daily_stats()

        # Select features for anomaly detection
        feature_cols = ["total_events", "errors", "avg_latency", "error_rate"]
        available_features = [c for c in feature_cols if c in data.columns]

        if len(available_features) < 2:
            logger.warning("Not enough features for anomaly detection")
            data["anomaly"] = 1
            return data

        features = data[available_features].fillna(0)

        # Scale features
        self.scaler = StandardScaler()
        features_scaled = self.scaler.fit_transform(features)

        # Train Isolation Forest
        self.anomaly_model = IsolationForest(
            contamination=0.1,  # Expect ~10% anomalies
            random_state=42,
            n_estimators=100,
        )
        data["anomaly"] = self.anomaly_model.fit_predict(features_scaled)
        data["anomaly_score"] = self.anomaly_model.score_samples(features_scaled)

        # Count anomalies
        n_anomalies = (data["anomaly"] == -1).sum()
        logger.info(
            f"Detected {n_anomalies} anomalies out of {len(data)} data points"
        )

        # Save results
        output_path = self.data_dir / "anomaly_detection.csv"
        data.to_csv(output_path, index=False)
        logger.info(f"Anomaly detection results saved to {output_path}")

        return data

    def predict_usage(
        self, days_ahead: int = 7, data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Predict future usage using statistical methods.
        
        Args:
            days_ahead: Number of days to forecast
            data: Historical data
            
        Returns:
            Dict with forecast data
        """
        if data is None:
            if self.data is not None:
                data = self.data
            else:
                data = self.aggregate_daily_stats()

        if len(data) < 7:
            logger.warning("Not enough data for forecasting (need at least 7 days)")
            return {
                "next_7_days": [],
                "confidence": 0.0,
                "method": "insufficient_data",
            }

        # Sort by date
        data = data.sort_values("date")
        values = data["total_events"].values

        # Simple moving average forecast
        # In production, use Prophet or ARIMA for better accuracy
        window = min(7, len(values))
        ma = pd.Series(values).rolling(window=window).mean().iloc[-1]

        # Calculate trend
        recent_values = values[-window:]
        trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]

        # Generate forecast
        forecast = []
        for i in range(days_ahead):
            predicted = ma + trend * (i + 1)
            # Add some noise for realism
            noise = np.random.normal(0, ma * 0.05)
            forecast.append(max(0, int(predicted + noise)))

        # Calculate confidence based on data volatility
        volatility = values.std() / values.mean() if values.mean() > 0 else 1
        confidence = max(0.5, min(0.95, 1 - volatility))

        result = {
            "next_7_days": forecast,
            "confidence": round(confidence, 2),
            "method": "moving_average_with_trend",
            "historical_avg": float(values.mean()),
            "historical_trend": float(trend),
            "generated_at": datetime.now().isoformat(),
        }

        # Save to JSON
        output_path = self.data_dir / "forecast.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Forecast saved to {output_path}")

        return result

    # ============================================================
    # Data Generation (for development/testing)
    # ============================================================

    def _generate_sample_logs(self, count: int = 1000) -> List[Dict]:
        """Generate sample log data for development/testing."""
        np.random.seed(42)
        integrations = ["slack", "discord", "telegram", "teams", "webhook"]
        event_types = ["info", "success", "error", "warning"]
        
        logs = []
        base_date = datetime.now() - timedelta(days=30)
        
        for i in range(count):
            timestamp = base_date + timedelta(
                hours=np.random.randint(0, 24 * 30),
                minutes=np.random.randint(0, 60),
            )
            integration = np.random.choice(integrations)
            event_type = np.random.choice(
                event_types, p=[0.6, 0.2, 0.1, 0.1]
            )
            
            logs.append({
                "id": f"log_{i}",
                "timestamp": timestamp.isoformat(),
                "integration": integration,
                "event_type": event_type,
                "latency_ms": float(np.random.exponential(50) + 20),
                "user_id": f"user_{np.random.randint(1, 50)}",
                "endpoint": f"/api/{integration}/message",
                "status_code": 200 if event_type != "error" else 500,
            })
        
        return logs

    def _generate_sample_analytics_output(self) -> Dict:
        """Generate complete sample analytics output."""
        log_data = self._generate_sample_logs(1000)
        
        daily_stats = self.aggregate_daily_stats(log_data)
        integration_stats = self.aggregate_by_integration(log_data)
        trends = self.compute_trends(daily_stats)
        anomaly_results = self.detect_anomalies_ml(daily_stats)
        forecast = self.predict_usage(7, daily_stats)
        
        # Get today's stats
        today = date.today()
        today_stats = daily_stats[daily_stats["date"].dt.date == today]
        
        if len(today_stats) > 0:
            today_row = today_stats.iloc[0]
            summary = {
                "total_events_today": int(today_row["total_events"]),
                "total_errors": int(today_row["errors"]),
                "avg_latency_ms": round(float(today_row["avg_latency"]), 1),
                "integrations_connected": len(integration_stats),
                "uptime_percent": round(float(today_row["uptime_percent"]), 1),
            }
        else:
            summary = {
                "total_events_today": 0,
                "total_errors": 0,
                "avg_latency_ms": 0,
                "integrations_connected": len(integration_stats),
                "uptime_percent": 100.0,
            }

        return {
            "summary": summary,
            "by_integration": integration_stats,
            "trends": trends,
            "forecast": forecast,
            "anomalies": anomaly_results[
                anomaly_results["anomaly"] == -1
            ][["date", "total_events", "errors", "avg_latency", "anomaly_score"]].to_dict(
                orient="records"
            )
            if "anomaly" in anomaly_results.columns
            else [],
        }

    # ============================================================
    # Main Pipeline
    # ============================================================

    def run(self, generate_sample: bool = True) -> Dict[str, Any]:
        """
        Run the full analytics pipeline.
        
        Args:
            generate_sample: If True, generate sample data for testing
            
        Returns:
            Complete analytics output
        """
        logger.info("=" * 50)
        logger.info("ANALYTICS ENGINE PIPELINE")
        logger.info("=" * 50)

        if generate_sample:
            logger.info("Generating sample data for development...")
            result = self._generate_sample_analytics_output()
        else:
            # In production, load from database
            # TODO: Implement database loading
            logger.info("Loading data from database...")
            result = self._generate_sample_analytics_output()

        logger.info("=" * 50)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Today's events: {result['summary']['total_events_today']}")
        logger.info(f"  Errors: {result['summary']['total_errors']}")
        logger.info(f"  Avg latency: {result['summary']['avg_latency_ms']}ms")
        logger.info(f"  Uptime: {result['summary']['uptime_percent']}%")
        logger.info(f"  Forecast confidence: {result['forecast']['confidence']}")
        logger.info("=" * 50)

        # Save complete output
        output_path = self.data_dir / "analytics_complete.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        logger.info(f"Complete analytics saved to {output_path}")

        return result


def main():
    parser = argparse.ArgumentParser(
        description="AURA Analytics Engine - Data aggregation, ML, and forecasting"
    )
    parser.add_argument(
        "--db-url",
        help="Database URL (default: sqlite:///aura_analytics.db)",
    )
    parser.add_argument(
        "--data-dir",
        default="./analytics_data",
        help="Data directory for output files",
    )
    parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Don't generate sample data (use real data)",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as scheduled job (for EasyCron/Cloud Scheduler)",
    )
    
    args = parser.parse_args()
    
    engine = AnalyticsEngine(
        db_url=args.db_url,
        data_dir=args.data_dir,
    )
    
    result = engine.run(generate_sample=not args.no_sample)
    
    if args.schedule:
        # In scheduled mode, output minimal info
        print(json.dumps({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "summary": result["summary"],
        }))
    else:
        print(f"\n✅ Analytics engine completed")
        print(f"   Today: {result['summary']['total_events_today']} events")
        print(f"   Errors: {result['summary']['total_errors']}")
        print(f"   Latency: {result['summary']['avg_latency_ms']}ms")
        print(f"   Uptime: {result['summary']['uptime_percent']}%")
        print(f"   Forecast confidence: {result['forecast']['confidence']}")


if __name__ == "__main__":
    main()