import sys
sys.path.insert(0, 'AURA_APP')
import gc
import tracemalloc
import asyncio
import logging
sys.stdout.reconfigure(encoding='utf-8')
from backend.aria_brain import AriaBrain

logger = logging.getLogger(__name__)


async def detect_leaks_brain():
    """Detect memory leaks in AriaBrain"""

    tracemalloc.start()
    gc.collect()

    baseline = tracemalloc.take_snapshot()

    brain = AriaBrain()

    for i in range(1000):
        await brain.think_and_decide(f"Test {i}")

        if i % 100 == 0:
            gc.collect()

    final = tracemalloc.take_snapshot()

    top_stats = final.compare_to(baseline, 'lineno')

    print("=" * 80)
    print("MEMORY LEAK DETECTION: AriaBrain")
    print("=" * 80)

    for stat in top_stats[:10]:
        print(stat)

    tracemalloc.stop()

    with open('memory_leaks.txt', 'w') as f:
        for stat in top_stats[:20]:
            f.write(str(stat) + '\n')


async def detect_leaks_connectors():
    """Detect memory leaks in connectors"""

    tracemalloc.start()
    gc.collect()

    baseline = tracemalloc.take_snapshot()

    for i in range(100):
        try:
            from backend.connectors.slack_connector import SlackConnector
            conn = SlackConnector()
            await conn.verify_connection()
            del conn
        except Exception:
            pass

        if i % 10 == 0:
            gc.collect()

    final = tracemalloc.take_snapshot()
    top_stats = final.compare_to(baseline, 'lineno')

    print("=" * 80)
    print("MEMORY LEAK DETECTION: Connectors")
    print("=" * 80)

    for stat in top_stats[:10]:
        print(stat)

    tracemalloc.stop()


if __name__ == '__main__':
    print("Memory Leak Detection...")
    asyncio.run(detect_leaks_brain())
    asyncio.run(detect_leaks_connectors())
    print("Leak detection completado")
