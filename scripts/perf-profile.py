#!/usr/bin/env python3

"""
AURA OS Performance Profiling

Profile CPU, memory, and I/O performance under load.
Run while backend is running at http://localhost:8000

Usage:
    .venv\Scripts\python.exe scripts/perf-profile.py
    .venv\Scripts\python.exe scripts/perf-profile.py --requests 50 --concurrency 10
"""

import argparse
import asyncio
import httpx
import psutil
import time
import json
from datetime import datetime


class PerformanceProfiler:
    """Profile AURA OS performance metrics"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.metrics = {
            "latency": [],
            "memory": [],
            "cpu": [],
            "errors": 0,
            "total_requests": 0,
        }
        self._process = None

    def _get_process(self):
        if self._process is None:
            self._process = psutil.Process()
        return self._process

    async def profile_chat_endpoint(self, num_requests=100):
        """Profile chat endpoint performance"""
        print("[*] Profiling chat endpoint...")
        print(f"[*] Running {num_requests} requests...")

        process = self._get_process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(num_requests):
                start = time.time()
                last_latency = 0.0

                try:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json={"message": f"Test message {i}"}
                    )

                    last_latency = (time.time() - start) * 1000  # ms
                    self.metrics["latency"].append(last_latency)
                    self.metrics["total_requests"] += 1

                    if response.status_code != 200:
                        self.metrics["errors"] += 1

                except Exception as e:
                    self.metrics["errors"] += 1
                    print(f"[-] Error: {e}")

                if i % 10 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    self.metrics["memory"].append(current_memory)
                    cpu_percent = process.cpu_percent(interval=0.1)
                    self.metrics["cpu"].append(cpu_percent)

                    print(
                        f"  [{i}/{num_requests}] "
                        f"Latency: {last_latency:.1f}ms, "
                        f"Memory: {current_memory:.1f}MB, "
                        f"CPU: {cpu_percent:.1f}%"
                    )

        final_memory = process.memory_info().rss / 1024 / 1024

        return {
            "total_requests": num_requests,
            "successful": num_requests - self.metrics["errors"],
            "errors": self.metrics["errors"],
            "memory_delta_mb": round(final_memory - initial_memory, 2),
            "memory_final_mb": round(final_memory, 2),
        }

    async def profile_health_endpoint(self, num_requests=100):
        """Profile health check endpoint performance"""
        print("\n[*] Profiling health endpoint...")

        async with httpx.AsyncClient(timeout=10) as client:
            latencies = []
            for i in range(num_requests):
                start = time.time()
                try:
                    await client.get(f"{self.base_url}/api/health")
                    latencies.append((time.time() - start) * 1000)
                except Exception:
                    pass

        print(f"  Health check: {len(latencies)}/{num_requests} OK")
        return latencies

    async def profile_concurrent_load(self, concurrency=20, duration=10):
        """Profile with concurrent requests"""
        print(f"\n[*] Profiling concurrent load ({concurrency} concurrent, {duration}s)...")

        async def worker(client, results):
            start = time.time()
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"message": "concurrent test"},
                    timeout=10.0
                )
                elapsed = (time.time() - start) * 1000
                results.append({
                    "status": response.status_code,
                    "latency_ms": elapsed,
                })
            except Exception as e:
                results.append({"status": 500, "latency_ms": (time.time() - start) * 1000, "error": str(e)})

        async with httpx.AsyncClient(timeout=30) as client:
            results = []
            tasks = []
            end_time = time.time() + duration

            while time.time() < end_time:
                task = asyncio.create_task(worker(client, results))
                tasks.append(task)
                if len(tasks) >= concurrency:
                    await asyncio.sleep(0.1)
                    done = [t for t in tasks if t.done()]
                    for t in done:
                        tasks.remove(t)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        successful = [r for r in results if r["status"] == 200]
        latencies = [r["latency_ms"] for r in successful]

        print(f"  Concurrent requests: {len(results)} total, {len(successful)} successful")
        if latencies:
            print(f"  Avg latency: {sum(latencies)/len(latencies):.1f}ms")
            print(f"  P95 latency: {sorted(latencies)[int(len(latencies)*0.95)]:.1f}ms")

        return {
            "total": len(results),
            "successful": len(successful),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2) if latencies else 0,
        }

    def generate_report(self):
        """Generate performance report"""
        if not self.metrics["latency"]:
            print("[-] No latency data collected")
            return None

        latencies = sorted(self.metrics["latency"])
        n = len(latencies)

        if n == 0:
            print("[-] No latency data")
            return None

        report = {
            "timestamp": datetime.now().isoformat(),
            "latency": {
                "min_ms": round(min(latencies), 2),
                "max_ms": round(max(latencies), 2),
                "mean_ms": round(sum(latencies) / n, 2),
                "median_ms": round(latencies[n // 2], 2),
                "p95_ms": round(latencies[int(n * 0.95)], 2),
                "p99_ms": round(latencies[int(n * 0.99)], 2),
            },
            "memory": {
                "min_mb": round(min(self.metrics["memory"]), 2) if self.metrics["memory"] else 0,
                "max_mb": round(max(self.metrics["memory"]), 2) if self.metrics["memory"] else 0,
                "mean_mb": round(sum(self.metrics["memory"]) / len(self.metrics["memory"]), 2) if self.metrics["memory"] else 0,
            },
            "cpu": {
                "min_percent": round(min(self.metrics["cpu"]), 2) if self.metrics["cpu"] else 0,
                "max_percent": round(max(self.metrics["cpu"]), 2) if self.metrics["cpu"] else 0,
                "mean_percent": round(sum(self.metrics["cpu"]) / len(self.metrics["cpu"]), 2) if self.metrics["cpu"] else 0,
            },
            "errors": self.metrics["errors"],
            "total_requests": self.metrics["total_requests"],
        }

        print("\n" + "=" * 70)
        print("AURA OS PERFORMANCE PROFILE")
        print("=" * 70)

        print("\nLatency Metrics (ms):")
        for key, value in report["latency"].items():
            print(f"  {key:<15} {value:>10.2f}")

        print("\nMemory Metrics (MB):")
        for key, value in report["memory"].items():
            print(f"  {key:<15} {value:>10.2f}")

        print("\nCPU Metrics (%):")
        for key, value in report["cpu"].items():
            print(f"  {key:<15} {value:>10.2f}")

        print(f"\nErrors: {report['errors']}")
        print(f"Total Requests: {report['total_requests']}")
        print("=" * 70)

        with open("PERFORMANCE_PROFILE.json", "w") as f:
            json.dump(report, f, indent=2)

        print("\n[+] Report saved to PERFORMANCE_PROFILE.json")
        return report


async def main():
    """Run performance profiling"""
    parser = argparse.ArgumentParser(description="AURA OS Performance Profiler")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()

    profiler = PerformanceProfiler(base_url=args.base_url)

    await profiler.profile_chat_endpoint(num_requests=args.requests)

    await profiler.profile_concurrent_load(
        concurrency=args.concurrency,
        duration=args.duration,
    )

    profiler.generate_report()


if __name__ == "__main__":
    asyncio.run(main())
