#!/usr/bin/env python3

"""
OMNIROUTE STRESS TEST

Load testing para validar:
- Comportamiento bajo carga
- Escalabilidad
- Límites del sistema
"""

import asyncio
import httpx
import time
import statistics
from datetime import datetime


class OmnirouteStressTest:
    """Stress testing para Omniroute"""

    def __init__(self, aura_url: str = "http://localhost:8000"):
        self.aura_url = aura_url
        self.results = []

    async def stress_test(self, duration_seconds: int = 60, concurrent_clients: int = 10):
        """
        Stress test durante N segundos con M clientes concurrentes.

        Mide:
        - Total de requests completados
        - Throughput (requests/sec)
        - Latencia bajo carga
        - Tasa de error
        """
        print(f"\n{'='*70}")
        print(f"OMNIROUTE STRESS TEST")
        print(f"Duration: {duration_seconds}s, Concurrent clients: {concurrent_clients}")
        print(f"{'='*70}")

        request_count = 0
        error_count = 0
        latencies = []
        start_time = time.time()

        async def client_task():
            nonlocal request_count, error_count

            while (time.time() - start_time) < duration_seconds:
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        req_start = time.time()

                        response = await client.post(
                            f"{self.aura_url}/api/chat/omniroute",
                            json={"message": "Stress test message"},
                            timeout=25,
                        )

                        latency = (time.time() - req_start) * 1000

                        if response.status_code == 200:
                            latencies.append(latency)
                            request_count += 1
                        else:
                            error_count += 1

                except asyncio.TimeoutError:
                    error_count += 1
                except Exception:
                    error_count += 1

        tasks = [client_task() for _ in range(concurrent_clients)]
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        print(f"\nResults:")
        print(f"  Total requests: {request_count}")
        print(f"  Total errors: {error_count}")
        print(f"  Success rate: {(request_count / (request_count + error_count) * 100):.1f}%")
        print(f"  Throughput: {(request_count / total_time):.2f} req/sec")

        if latencies:
            print(f"  Avg latency: {statistics.mean(latencies):.2f}ms")
            print(f"  P50 latency: {statistics.quantiles(latencies, n=4)[1]:.2f}ms")
            if len(latencies) >= 20:
                print(f"  P95 latency: {statistics.quantiles(latencies, n=20)[18]:.2f}ms")
            if len(latencies) >= 100:
                print(f"  P99 latency: {statistics.quantiles(latencies, n=100)[98]:.2f}ms")
            print(f"  Max latency: {max(latencies):.2f}ms")

        return {
            "duration_seconds": duration_seconds,
            "concurrent_clients": concurrent_clients,
            "total_requests": request_count,
            "total_errors": error_count,
            "throughput_rps": request_count / total_time,
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
        }


async def main():
    """Ejecutar stress test"""
    stress = OmnirouteStressTest()

    print("\n" + "=" * 70)
    print("TEST 1: Light Load (30s, 5 clients)")
    print("=" * 70)
    await stress.stress_test(duration_seconds=30, concurrent_clients=5)

    print("\n" + "=" * 70)
    print("TEST 2: Medium Load (60s, 10 clients)")
    print("=" * 70)
    await stress.stress_test(duration_seconds=60, concurrent_clients=10)

    print("\n" + "=" * 70)
    print("TEST 3: Heavy Load (60s, 20 clients)")
    print("=" * 70)
    await stress.stress_test(duration_seconds=60, concurrent_clients=20)

    print(f"\n{'='*70}")
    print("✅ Stress test complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
