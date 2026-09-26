import cProfile
import pstats
import io
import asyncio
import sys
sys.path.insert(0, 'AURA_APP')
sys.stdout.reconfigure(encoding='utf-8')

from backend.aria_brain import AriaBrain
from backend.connectors.base import ConnectorBase


def profile_think():
    """Profile AriaBrain.think_and_decide"""
    brain = AriaBrain()

    pr = cProfile.Profile()
    pr.enable()

    for _ in range(100):
        asyncio.run(brain.think_and_decide("Test situation"))

    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)

    print("=" * 80)
    print("PROFILING: AriaBrain.think_and_decide")
    print("=" * 80)
    print(s.getvalue())

    with open('profile_think.txt', 'w') as f:
        f.write(s.getvalue())


def profile_connectors():
    """Profile connector initialization"""
    pr = cProfile.Profile()
    pr.enable()

    for _ in range(50):
        try:
            conn = ConnectorBase()
            asyncio.run(conn.verify_connection())
        except Exception:
            pass

    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)

    print("=" * 80)
    print("PROFILING: Connector Initialization")
    print("=" * 80)
    print(s.getvalue())

    with open('profile_connectors.txt', 'w') as f:
        f.write(s.getvalue())


def profile_memory():
    """Profile memory usage"""
    import tracemalloc

    tracemalloc.start()

    brain = AriaBrain()
    current, peak = tracemalloc.get_traced_memory()

    print("=" * 80)
    print("MEMORY PROFILING: AriaBrain Initialization")
    print("=" * 80)
    print(f"Current memory: {current / 1024 / 1024:.2f} MB")
    print(f"Peak memory: {peak / 1024 / 1024:.2f} MB")

    tracemalloc.stop()

    with open('profile_memory.txt', 'w') as f:
        f.write(f"Current memory: {current / 1024 / 1024:.2f} MB\n")
        f.write(f"Peak memory: {peak / 1024 / 1024:.2f} MB\n")


if __name__ == '__main__':
    print("Performance Profiling...")
    profile_think()
    profile_connectors()
    profile_memory()
    print("Profiling completado")
