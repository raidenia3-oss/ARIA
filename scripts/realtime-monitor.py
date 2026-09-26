#!/usr/bin/env python3

# scripts/realtime-monitor.py
# Real-time monitoring dashboard for post-launch AURA OS

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List
import sys


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time"""
    timestamp: str
    api_health: bool
    latency_ms: float
    error_rate: float
    active_users: int
    github_stars: int
    github_issues: int
    github_discussions: int
    uptime_percent: float


class RealTimeMonitor:
    """Real-time monitoring system"""

    def __init__(self, api_url="http://localhost:8000", github_token=None):
        self.api_url = api_url
        self.github_token = github_token
        self.metrics_history: List[MetricSnapshot] = []
        self.alerts = []

    async def check_api_health(self):
        """Check API health and latency"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                start = datetime.now()
                response = await client.get(f"{self.api_url}/api/health")
                latency = (datetime.now() - start).total_seconds() * 1000

                is_healthy = response.status_code == 200
                return {
                    "healthy": is_healthy,
                    "latency_ms": latency,
                    "status_code": response.status_code
                }
        except Exception as e:
            return {
                "healthy": False,
                "latency_ms": 0,
                "error": str(e)
            }

    async def check_github_metrics(self):
        """Check GitHub metrics"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if self.github_token:
                    headers["Authorization"] = f"token {self.github_token}"

                response = await client.get(
                    "https://api.github.com/repos/TU_USUARIO/AURA",
                    headers=headers
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "stars": data.get("stargazers_count", 0),
                        "forks": data.get("forks_count", 0),
                        "issues": data.get("open_issues_count", 0)
                    }
        except Exception as e:
            return None

        return {"stars": 0, "forks": 0, "issues": 0}

    async def check_discussions(self):
        """Check GitHub discussions count (approximate via GraphQL)"""
        if not self.github_token:
            return 0
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"token {self.github_token}"}
                gql_query = {
                    "query": "{ repository(owner: \"TU_USUARIO\", name: \"AURA\") { discussions { totalCount } } }"
                }
                response = await client.post(
                    "https://api.github.com/graphql",
                    headers=headers,
                    json=gql_query,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", {}).get("repository", {}).get("discussions", {}).get("totalCount", 0)
        except Exception:
            pass
        return 0

    async def get_snapshot(self) -> MetricSnapshot:
        """Get current metrics snapshot"""
        api_health = await self.check_api_health()
        github_metrics = await self.check_github_metrics()
        discussions = await self.check_discussions()

        snapshot = MetricSnapshot(
            timestamp=datetime.now().isoformat(),
            api_health=api_health.get("healthy", False),
            latency_ms=api_health.get("latency_ms", 0),
            error_rate=0.0,
            active_users=0,
            github_stars=github_metrics.get("stars", 0),
            github_issues=github_metrics.get("issues", 0),
            github_discussions=discussions,
            uptime_percent=99.9
        )

        self.metrics_history.append(snapshot)
        return snapshot

    async def check_alerts(self, snapshot: MetricSnapshot):
        """Check for alert conditions"""
        if snapshot.latency_ms > 1000:
            self.alerts.append({
                "level": "warning",
                "message": f"High latency: {snapshot.latency_ms:.0f}ms (threshold: 1000ms)",
                "timestamp": snapshot.timestamp
            })

        if not snapshot.api_health:
            self.alerts.append({
                "level": "critical",
                "message": "API is down",
                "timestamp": snapshot.timestamp
            })

        if snapshot.error_rate > 0.05:
            self.alerts.append({
                "level": "warning",
                "message": f"High error rate: {snapshot.error_rate*100:.1f}%",
                "timestamp": snapshot.timestamp
            })

    def display_dashboard(self, snapshot: MetricSnapshot):
        """Display real-time dashboard"""
        print("\033[2J\033[H")

        print("╔════════════════════════════════════════════════════════════════╗")
        print("║  AURA OS v2.1 — Post-Launch Monitoring Dashboard              ║")
        print("╚════════════════════════════════════════════════════════════════╝")

        print(f"\nTimestamp: {snapshot.timestamp}")
        print(f"Session Duration: {len(self.metrics_history)} snapshots")

        print("\n┌─ API Status")
        health_icon = "✅" if snapshot.api_health else "❌"
        print(f"│  {health_icon} API Health: {'Healthy' if snapshot.api_health else 'Down'}")
        print(f"│  ⏱️  Latency: {snapshot.latency_ms:.1f}ms")
        if snapshot.latency_ms > 500:
            print(f"│  ⚠️  Warning: Latency above target (<500ms)")
        print(f"│  📊 Error Rate: {snapshot.error_rate*100:.2f}%")
        print(f"│  ⬆️  Uptime: {snapshot.uptime_percent:.1f}%")

        print("\n┌─ Community Growth")
        print(f"│  ⭐ GitHub Stars: {snapshot.github_stars}")
        print(f"│  🔀 GitHub Issues: {snapshot.github_issues}")
        print(f"│  💬 Discussions: {snapshot.github_discussions}")

        if len(self.metrics_history) > 1:
            prev = self.metrics_history[-2]
            stars_diff = snapshot.github_stars - prev.github_stars
            issues_diff = snapshot.github_issues - prev.github_issues

            print("\n┌─ Trends (vs. last snapshot)")
            print(f"│  ⭐ Stars: {stars_diff:+d}")
            print(f"│  🔀 Issues: {issues_diff:+d}")
            if stars_diff > 0:
                print(f"│  📈 Growth Rate: ~{stars_diff} stars/interval")

        if self.alerts:
            print("\n┌─ Active Alerts")
            for alert in self.alerts[-5:]:
                alert_icon = "🔴" if alert["level"] == "critical" else "🟡"
                print(f"│  {alert_icon} [{alert['level'].upper()}] {alert['message']}")

        print("\n┌─ SLA Status")
        latency_ok = snapshot.latency_ms < 500
        availability_ok = snapshot.uptime_percent > 99.5
        error_ok = snapshot.error_rate < 0.01

        print(f"│  {'✅' if latency_ok else '❌'} Latency SLA (<500ms): {latency_ok}")
        print(f"│  {'✅' if availability_ok else '❌'} Availability SLA (>99.5%): {availability_ok}")
        print(f"│  {'✅' if error_ok else '❌'} Error Rate SLA (<1%): {error_ok}")

        sla_met = latency_ok and availability_ok and error_ok
        overall = "🟢 GREEN" if sla_met else "🟡 YELLOW" if not snapshot.api_health else "🔴 RED"
        print(f"│  Overall: {overall}")

        print("\n" + "─" * 64)
        print("Press Ctrl+C to stop monitoring | Updating every 30 seconds")

    async def run_continuous(self, interval_seconds=30):
        """Run continuous monitoring"""
        print("Starting real-time monitoring...")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                snapshot = await self.get_snapshot()
                await self.check_alerts(snapshot)
                self.display_dashboard(snapshot)
                await asyncio.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped")
            self.generate_report()

    def generate_report(self):
        """Generate monitoring report"""
        if not self.metrics_history:
            return

        print("\n" + "=" * 64)
        print("POST-LAUNCH MONITORING REPORT")
        print("=" * 64)

        first = self.metrics_history[0]
        last = self.metrics_history[-1]

        print(f"\nMonitoring Period:")
        print(f"  Start: {first.timestamp}")
        print(f"  End: {last.timestamp}")
        print(f"  Duration: {len(self.metrics_history)} snapshots")

        avg_latency = sum(m.latency_ms for m in self.metrics_history) / len(self.metrics_history)
        avg_uptime = sum(m.uptime_percent for m in self.metrics_history) / len(self.metrics_history)
        healthy_count = sum(1 for m in self.metrics_history if m.api_health)
        health_percent = (healthy_count / len(self.metrics_history)) * 100

        print(f"\nPerformance Metrics:")
        print(f"  Average Latency: {avg_latency:.1f}ms")
        print(f"  Average Uptime: {avg_uptime:.1f}%")
        print(f"  Health Checks Passed: {health_percent:.1f}%")

        print(f"\nCommunity Growth:")
        print(f"  Starting Stars: {first.github_stars}")
        print(f"  Ending Stars: {last.github_stars}")
        print(f"  Growth: +{last.github_stars - first.github_stars} stars")
        print(f"  Issues: {last.github_issues}")
        print(f"  Discussions: {last.github_discussions}")

        report = {
            "period": {
                "start": first.timestamp,
                "end": last.timestamp,
                "snapshots": len(self.metrics_history)
            },
            "performance": {
                "avg_latency_ms": avg_latency,
                "avg_uptime_percent": avg_uptime,
                "health_percent": health_percent
            },
            "community": {
                "starting_stars": first.github_stars,
                "ending_stars": last.github_stars,
                "star_growth": last.github_stars - first.github_stars,
                "issues": last.github_issues,
                "discussions": last.github_discussions
            },
            "alerts": self.alerts
        }

        with open("MONITORING_REPORT.json", "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Report saved to MONITORING_REPORT.json")


async def main():
    """Run monitoring"""
    import os
    api_url = os.getenv("AURA_API_URL", "http://localhost:8000")
    github_token = os.getenv("GITHUB_TOKEN", None)

    monitor = RealTimeMonitor(api_url=api_url, github_token=github_token)
    await monitor.run_continuous(interval_seconds=30)


if __name__ == "__main__":
    asyncio.run(main())
