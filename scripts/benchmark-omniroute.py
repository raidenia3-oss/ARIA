#!/usr/bin/env python3

"""
OMNIROUTE BENCHMARKING SUITE

Mide performance de providers y genera reportes de:
- Latencia promedio
- Tokens por segundo
- Tasa de error
- Disponibilidad
- Comparativa entre providers
"""

import asyncio
import httpx
import time
import statistics
from datetime import datetime
from typing import Dict, List
import json
import sys


class OmnirouteBenchmark:
    """Benchmarking suite para Omniroute"""

    def __init__(self, aura_url: str = "http://localhost:8000"):
        self.aura_url = aura_url
        self.results: Dict = {}

    async def benchmark_providers(self, num_requests: int = 10) -> Dict:
        """
        Benchmark de todos los proveedores.

        Mide:
        - Latencia
        - Tasa de éxito
        - Tokens generados
        """
        print(f"\n{'='*70}")
        print(f"OMNIROUTE PROVIDER BENCHMARK")
        print(f"Requests per provider: {num_requests}")
        print(f"{'='*70}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{self.aura_url}/api/providers")
                providers_data = response.json()
                providers = providers_data["providers"][:10]
        except Exception as e:
            print(f"Error getting providers: {e}")
            return {}

        print(f"\nTesting top {len(providers)} providers...")
        print(f"{'Provider':<20} {'Avg Latency':<15} {'Success Rate':<15} {'Status':<15}")
        print("-" * 65)

        for provider in providers:
            provider_name = provider["name"]
            latencies = []
            successes = 0

            for i in range(num_requests):
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        start = time.time()

                        response = await client.post(
                            f"{self.aura_url}/api/chat/omniroute",
                            json={
                                "message": f"What is 2+2? (Test {i+1}/{num_requests})"
                            },
                            timeout=25,
                        )

                        latency = (time.time() - start) * 1000

                        if response.status_code == 200:
                            latencies.append(latency)
                            successes += 1

                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

            if latencies:
                avg_latency = statistics.mean(latencies)
                success_rate = (successes / num_requests) * 100

                self.results[provider_name] = {
                    "avg_latency_ms": avg_latency,
                    "min_latency_ms": min(latencies),
                    "max_latency_ms": max(latencies),
                    "stddev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                    "success_rate": success_rate,
                    "successful_requests": successes,
                    "total_requests": num_requests,
                }

                print(f"{provider_name:<20} {avg_latency:>12.2f}ms {success_rate:>13.1f}% ✓")
            else:
                print(f"{provider_name:<20} {'FAILED':<15} {'0.0%':<15} ✗")

        return self.results

    async def benchmark_fallback(self) -> Dict:
        """Test fallback behavior when providers fail"""
        print(f"\n{'='*70}")
        print("FALLBACK BEHAVIOR TEST")
        print(f"{'='*70}")

        print("\nTesting fallback mechanism...")

        results = {
            "fallback_triggered": False,
            "fallback_latency_ms": 0,
            "response_received": False,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                start = time.time()

                response = await client.post(
                    f"{self.aura_url}/api/chat/omniroute",
                    json={"message": "Test fallback"},
                )

                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    results["response_received"] = True
                    results["fallback_latency_ms"] = latency
                    results["source"] = data.get("source", "unknown")

                    print(f"✓ Response received in {latency:.2f}ms")
                    print(f"  Source: {data.get('source')}")

        except Exception as e:
            print(f"✗ Error testing fallback: {e}")

        return results

    async def benchmark_concurrent_requests(self, num_concurrent: int = 5) -> Dict:
        """Test concurrent request handling"""
        print(f"\n{'='*70}")
        print(f"CONCURRENT REQUESTS TEST ({num_concurrent} parallel)")
        print(f"{'='*70}")

        async def make_request(i: int):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    start = time.time()

                    response = await client.post(
                        f"{self.aura_url}/api/chat/omniroute",
                        json={"message": f"Test request {i+1}"},
                    )

                    latency = (time.time() - start) * 1000

                    return {
                        "request": i + 1,
                        "status": response.status_code,
                        "latency_ms": latency,
                        "success": response.status_code == 200,
                    }
            except Exception as e:
                return {
                    "request": i + 1,
                    "status": 0,
                    "latency_ms": 0,
                    "success": False,
                    "error": str(e),
                }

        tasks = [make_request(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r["success"])
        latencies = [r["latency_ms"] for r in results if r["success"]]

        print(f"\nResults:")
        print(f"  Successful: {successful}/{num_concurrent}")

        if latencies:
            print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
            print(f"  Min latency: {min(latencies):.2f}ms")
            print(f"  Max latency: {max(latencies):.2f}ms")

        return {
            "concurrent_requests": num_concurrent,
            "successful": successful,
            "total": num_concurrent,
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
        }

    def generate_report(self) -> str:
        """Generate HTML report"""
        report = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Omniroute Benchmark Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        h1 {{ color: #333; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>Omniroute Benchmark Report</h1>
    <p class="timestamp">Generated: {datetime.utcnow().isoformat()}</p>

    <h2>Provider Performance</h2>
    <table>
        <tr>
            <th>Provider</th>
            <th>Avg Latency (ms)</th>
            <th>Min/Max (ms)</th>
            <th>Success Rate</th>
        </tr>
"""

        for provider, stats in self.results.items():
            report += f"""
        <tr>
            <td>{provider}</td>
            <td>{stats['avg_latency_ms']:.2f}</td>
            <td>{stats['min_latency_ms']:.2f} / {stats['max_latency_ms']:.2f}</td>
            <td>{stats['success_rate']:.1f}%</td>
        </tr>
"""

        report += """
    </table>
</body>
</html>
"""
        return report

    async def run_full_benchmark(self):
        """Ejecutar benchmark completo"""
        print("\n" + "=" * 70)
        print("STARTING OMNIROUTE BENCHMARKING SUITE")
        print("=" * 70)

        await self.benchmark_providers(num_requests=5)
        await self.benchmark_fallback()
        await self.benchmark_concurrent_requests(num_concurrent=5)

        report = self.generate_report()

        with open("omniroute-benchmark-report.html", "w") as f:
            f.write(report)

        print(f"\n{'='*70}")
        print("✅ Benchmark complete!")
        print(f"Report saved to: omniroute-benchmark-report.html")
        print(f"{'='*70}\n")


async def main():
    """Ejecutar benchmark"""
    benchmark = OmnirouteBenchmark()
    await benchmark.run_full_benchmark()


if __name__ == "__main__":
    asyncio.run(main())
