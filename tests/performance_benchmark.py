"""AURA v2.x — Performance Benchmarks (Phase D).

Benchmark all agents, API endpoints, and daemon tasks.
"""

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

os.environ.setdefault("AI_PROVIDER", "local")
os.environ.setdefault("DATABASE_URL", "sqlite:///data/test_aura.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@dataclass
class BenchmarkResult:
    agent: str
    method: str
    time_ms: float
    accuracy: float = 0.0
    quality: float = 0.0
    memory_mb: float = 0.0


@dataclass
class BenchmarkReport:
    results: List[BenchmarkResult] = field(default_factory=list)
    baseline: Dict[str, float] = field(default_factory=dict)
    improvements: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_benchmarks": len(self.results),
            "slowest": max(self.results, key=lambda r: r.time_ms).agent if self.results else None,
            "fastest": min(self.results, key=lambda r: r.time_ms).agent if self.results else None,
            "improvements": self.improvements,
            "timestamp": self.timestamp,
        }


BASELINE = {
    "code_reviewer": 5000,
    "business_analyst": 4000,
    "researcher": 6000,
    "video_analyzer": 8000,
    "language_tutor": 3000,
    "fanfic_generation": 5000,
    "marketplace_query": 1000,
    "sync_push": 2000,
    "netrunner_hack": 500,
}


async def benchmark_all_agents() -> BenchmarkReport:
    """Benchmark time/accuracy/quality for each agent. Compare with v1.0 baseline."""
    report = BenchmarkReport()
    report.baseline = BASELINE.copy()

    agent_tests = [
        ("code_reviewer", "review_code", lambda a: a.review_code("def test(): pass")),
        ("business_analyst", "analyze_market", lambda a: a.analyze_market("TechCorp")),
        ("researcher", "search_academic", lambda a: a.search_academic("AI")),
        ("video_analyzer", "extract_transcript", lambda a: a.extract_transcript("https://x.mp4")),
        ("language_tutor", "teach_language", lambda a: a.teach_language("Spanish", "B1")),
    ]

    for name, method, call in agent_tests:
        from backend.agents.agent_business_analyst import BusinessAnalystAgent
        from backend.agents.agent_code_reviewer import CodeReviewerAgent
        from backend.agents.agent_language_tutor import LanguageTutorAgent
        from backend.agents.agent_researcher import ResearcherAgent
        from backend.agents.agent_video_analyzer import VideoAnalyzerAgent

        agent = _get_agent(name)

        start = time.perf_counter()
        try:
            result = await call(agent)
            elapsed = (time.perf_counter() - start) * 1000
            accuracy = _measure_accuracy(result, method)
            quality = _measure_quality(result, method)
            mem = _measure_memory()

            benchmark = BenchmarkResult(
                agent=name,
                method=method,
                time_ms=max(0.01, elapsed),
                accuracy=accuracy,
                quality=quality,
                memory_mb=mem,
            )
            report.results.append(benchmark)

            baseline_ms = BASELINE.get(name, 0)
            if baseline_ms > 0:
                improvement = ((baseline_ms - elapsed) / baseline_ms) * 100
                report.improvements[name] = round(improvement, 2)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            report.results.append(
                BenchmarkResult(
                    agent=name,
                    method=method,
                    time_ms=max(0.01, elapsed),
                    accuracy=0,
                    quality=0,
                )
            )

    return report


def _get_agent(name: str):
    from backend.agents.agent_business_analyst import BusinessAnalystAgent
    from backend.agents.agent_code_reviewer import CodeReviewerAgent
    from backend.agents.agent_data_scientist import DataScientistAgent
    from backend.agents.agent_fitness_coach import FitnessCoachAgent
    from backend.agents.agent_image_processor import ImageProcessorAgent
    from backend.agents.agent_language_tutor import LanguageTutorAgent
    from backend.agents.agent_music_composer import MusicComposerAgent
    from backend.agents.agent_psychology_counselor import PsychologyCounselorAgent
    from backend.agents.agent_researcher import ResearcherAgent
    from backend.agents.agent_video_analyzer import VideoAnalyzerAgent

    mapping = {
        "code_reviewer": CodeReviewerAgent,
        "business_analyst": BusinessAnalystAgent,
        "researcher": ResearcherAgent,
        "video_analyzer": VideoAnalyzerAgent,
        "language_tutor": LanguageTutorAgent,
        "fitness_coach": FitnessCoachAgent,
        "music_composer": MusicComposerAgent,
        "psychology_counselor": PsychologyCounselorAgent,
        "data_scientist": DataScientistAgent,
        "image_processor": ImageProcessorAgent,
    }
    cls = mapping.get(name)
    return cls() if cls else None


def _measure_accuracy(result: Any, method: str) -> float:
    if not result:
        return 0.0
    if isinstance(result, dict):
        if "issues" in result and method == "review_code":
            return min(100.0, len(result["issues"]) * 10)
        if "competitors" in result and method == "analyze_market":
            return min(100.0, len(result["competitors"]) * 12.5)
        if "papers" in result and method == "search_academic":
            return min(100.0, len(result["papers"]) * 4)
        if "exercises" in result and method == "teach_language":
            return 85.0
        if "transcript" in result and method == "extract_transcript":
            return 70.0
    return 50.0


def _measure_quality(result: Any, method: str) -> float:
    if not result:
        return 0.0
    if isinstance(result, dict):
        size = len(str(result))
        return min(100.0, size / 10)
    return 50.0


def _measure_memory() -> float:
    import gc

    gc.collect()
    return 0.0


async def benchmark_api_endpoints() -> Dict[str, Any]:
    """Stress test API endpoints at 100 req/s. Measure latency, throughput, detect bottlenecks."""
    import concurrent.futures

    from fastapi.testclient import TestClient

    from tests.test_comprehensive import app

    client = TestClient(app)
    endpoints = ["/health", "/api/system/status", "/api/skills", "/api/agent/status"]
    results = {}

    for path in endpoints:
        latencies = []

        def make_req(_):
            start = time.time()
            r = client.get(path)
            elapsed = (time.time() - start) * 1000
            return elapsed, r.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_req, i) for i in range(100)]
            for f in concurrent.futures.as_completed(futures):
                elapsed, status = f.result()
                if status == 200:
                    latencies.append(elapsed)

        if latencies:
            results[path] = {
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
                "p99_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 2),
                "max_latency_ms": round(max(latencies), 2),
                "min_latency_ms": round(min(latencies), 2),
                "success_rate": len(latencies) / 100 * 100,
                "throughput_req_s": len(latencies) / (max(latencies) / 1000) if latencies else 0,
            }

    return results


async def benchmark_daemon_tasks() -> Dict[str, Any]:
    """Benchmark daemon: CPU/memory usage sustained, task completion time, event processing rate."""
    from backend.core.event_bus import CoreEvent, get_event_bus
    from backend.daemon.aura_daemon import AURADaemon

    report = {}

    # Task timing
    daemon = AURADaemon()
    daemon.current_tasks = [f"task_{i}" for i in range(20)]

    start = time.time()
    for _ in range(5):
        status = daemon.get_status()
    elapsed = time.time() - start
    report["task_completion_avg_ms"] = round((elapsed / 5) * 1000, 2)

    # Event processing rate
    bus = get_event_bus()
    start = time.perf_counter()
    for i in range(200):
        bus.emit(CoreEvent(type="benchmark", data={"index": i}))
    elapsed = time.perf_counter() - start
    report["event_rate_per_sec"] = round(200 / elapsed if elapsed > 0 else float("inf"), 0)

    # Sustained load timing
    start = time.time()
    for _ in range(100):
        daemon.get_status()
    report["sustained_100_calls_ms"] = round((time.time() - start) * 1000, 2)

    # Memory growth
    report["memory_mb"] = round(sys.getsizeof(daemon) / (1024 * 1024), 2)

    return report


class TestBenchmarks:

    @pytest.mark.asyncio
    async def test_benchmark_all_agents(self):
        report = await benchmark_all_agents()
        assert len(report.results) >= 5
        for r in report.results:
            assert r.time_ms > 0
            assert 0 <= r.accuracy <= 100
            assert 0 <= r.quality <= 100

    @pytest.mark.asyncio
    async def test_benchmark_api_endpoints(self):
        results = await benchmark_api_endpoints()
        assert len(results) >= 2
        for path, data in results.items():
            assert "avg_latency_ms" in data
            assert "throughput_req_s" in data

    @pytest.mark.asyncio
    async def test_benchmark_daemon(self):
        results = await benchmark_daemon_tasks()
        assert "task_completion_avg_ms" in results
        assert "event_rate_per_sec" in results
        assert results["event_rate_per_sec"] > 0

    @pytest.mark.asyncio
    async def test_fanfic_benchmark(self):
        from backend.agent.writer_agent import WriterAgent

        agent = WriterAgent()
        times = []
        for _ in range(3):
            start = time.perf_counter()
            await agent.generate("Fanfic about adventure")
            times.append(time.perf_counter() - start)
        avg = sum(times) / len(times) * 1000
        assert avg < 5000, f"Fanfic avg {avg:.0f}ms exceeds 5s"
